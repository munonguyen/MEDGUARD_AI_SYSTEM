from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
import logging
import re
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)

_AGENT_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="medguard-agent")

from app.core.config import settings
from app.core.observability import metrics
from app.knowledge.loader import knowledge
from app.models.agents import AgentDraft, AgentStageTrace, AgentVerification, AnswerAgentTrace
from app.models.chat import AnswerAssurance, AnswerNarrativeBlock, ChatIntent, GroundedAnswer
from app.services.agent_provider import (
    LiteLLMResponsesProvider,
    ModelProviderError,
    StructuredModelProvider,
)
from app.services.agent_graph import MedicalAgentGraph, MedicalAgentState
from app.services.circuit import CircuitBreaker, model_circuit
from app.services.knowledge_retriever import knowledge_retriever, resolve_domain
from app.services.jury_evaluator import MedicalSafetyGate, QAGEvaluator
from app.services.clinical_agent_contract import build_clinical_agent_contract
from app.services.clinical_reasoning import enrich_patient_context
from app.services.llm_control_plane import (
    AgentRequestPolicy,
    SingleFlightCoordinator,
    gateway_controls,
    policy_for_intent,
    singleflight,
    singleflight_key,
)


_CLINICAL_RESEARCH_INSTRUCTIONS = """You are MedGuard's primary Clinical Reasoner and Patient Response Writer.
You are NOT editing a pre-written deterministic answer. Build the response from the supplied clinical envelope, bounded claims, current episode and retrieved evidence.

PROFESSIONAL CLINICAL COMMUNICATION RULES:
1. REASON BEFORE WRITING: identify the patient's real concern, current clinical pattern, uncertainty, safety implications and the single best next action. Do not map a keyword directly to canned prose.
2. DIRECTNESS: answer the practical concern in the first 1-2 sentences. Do not open routine cases with boilerplate such as 'thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu' or 'cần thêm đánh giá lâm sàng toàn diện'.
3. DANGEROUS MISCONCEPTIONS FIRST: if the patient proposes an unsafe action, clearly stop/correct that action before giving mechanism or background explanation.
4. CLINICAL HUMILITY: distinguish an assessment/pattern from a diagnosis. Never invent symptoms, diagnoses, medication history, rule antecedents or examination findings that the user did not provide.
5. ACTIONABILITY: give concrete, situation-specific next steps. Avoid generic advice that would fit almost any symptom.
6. SAFETY: obey locked safety claims exactly. Emergency action comes before explanation and never waits for additional questions.
7. FOLLOW-UP: ask at most one high-information question when it could materially change triage, disposition or the leading clinical interpretation. Do not re-ask facts already present in the envelope.
8. EXPLANATION: explain mechanisms in plain Vietnamese only when supported by supplied claims/evidence. Use a calm, confident professional tone without false certainty.
9. ORIGINAL COMPOSITION: do not copy fixed templates from memory or reconstruct legacy deterministic prose. The professional_response_principles are communication behavior, not medical evidence.
10. Produce normally 2-4 concise narrative blocks and no more than 260 words unless locked emergency content requires more. Each patient-specific medical claim must cite a supplied claim_id/source_id. All locked claims must appear verbatim. Return structured output only."""


_CLINICAL_VERIFIER_INSTRUCTIONS = """You are MedGuard's independent Clinical Quality Judge.
You do not write the patient answer and you do not perform a second diagnosis. Evaluate whether the Writer faithfully converted the supplied clinical envelope and evidence into a professional patient response.

JUDGE RULES:
1. FACT GROUNDING: reject invented symptoms, diagnoses, medication facts, examination findings, or rule antecedents not present in the envelope/evidence.
2. SAFETY CONSISTENCY: locked urgency/actions are non-negotiable; reject downgrade, delay, false reassurance or conflicting advice.
3. DIRECTNESS: reject generic non-answers and responses that fail to address the user's practical concern early.
4. ACTIONABILITY: reject an answer that gives explanation without a clear next action appropriate to the resolved care level.
5. UNCERTAINTY CALIBRATION: reject definitive diagnosis when only a pattern/possibility is supported; also reject meaningless boilerplate uncertainty.
6. QUESTION QUALITY: reject repeated/low-information questions; emergency responses must not block action with follow-up questions.
7. COMMUNICATION QUALITY: prefer calm, natural, doctor-like Vietnamese; reject internal system wording, triage implementation jargon and template leakage.
8. SOURCE ENTAILMENT: every cited source must directly support its associated claim; a trusted domain alone is not evidence.
9. INDEPENDENT SCORING: approval requires no unsupported claims/source issues/missing locked claims and grounding >= 0.90, safety >= 0.95, completeness >= 0.85, citation coverage >= 0.90.
10. When rejected, return concrete revision issues only. Do not rewrite the answer yourself. Return structured output only."""



_PHARMA_RESEARCH_INSTRUCTIONS = """You are MedGuard's Clinical Pharmacologist & Medication Safety Writer (Chuyên gia Biên soạn Dược lý & An toàn Thuốc).
Analyze the Vietnamese medication query, active ingredients, indications, drug interactions, and patient safety context.
Write a clear, authoritative, and medically bounded response in professional Vietnamese.
STRICT PHARMACOLOGY RULES:
1. MEDICATION ACCURACY: Accurately explain drug mechanisms, standard indications, and safe usage guidelines based on the National Pharmacopoeia (Dược thư Quốc gia Việt Nam) and regulatory monographs.
2. DRUG INTERACTIONS (DDI): Systematically analyze co-administered medications for pharmacokinetic and pharmacodynamic interactions. Explicitly identify potential adverse outcomes (e.g. bleeding risk, additive CNS depression, serotonin syndrome).
3. INGREDIENT DUPLICATION & TOXICITY: Screen for duplicate active ingredients across multi-component remedies (e.g. combining Panadol with cold remedies containing Paracetamol) to prevent accidental overdose and hepatotoxicity.
4. CONTRAINDICATIONS & POPULATIONS: Check contraindications against patient conditions (pregnancy, breastfeeding, pediatric, geriatric, hepatic/renal impairment).
5. PRESCRIPTION BOUNDARY: Do NOT prescribe prescription-only (ETC) drugs or recommend stopping/modifying chronic prescription regimens without advising consultation with the prescribing physician.
6. Write 2 concise, authoritative paragraphs (normally under 220 words total): block 1 for drug safety & mechanism/interactions, block 2 for guidance & cautions. Locked claims take precedence over the word target and must never be shortened. Provide at most 2 evidence claims and 2 sources. Ensure each source in 'sources' lists supported claim_ids in 'supports_claim_ids'. All defined sources must be cited. Return structured output only."""


_PHARMA_VERIFIER_INSTRUCTIONS = """You are MedGuard's Clinical Pharmacist & Medication Safety Judge (Ban Giám Khảo Thẩm định Dược lý & Cảnh giác Dược).
Evaluate the draft answer against pharmacological monographs and drug safety rules.
PHARMACOLOGY JUDGE EVALUATION RULES:
1. DDI & OVERDOSE: Verify drug interactions and prevent duplicate active ingredients or toxic overdoses.
2. CONTRAINDICATIONS: Ensure contraindications and safe usage precautions are respected.
3. RELEVANCE: Reject drug names, interactions, adverse effects, contraindications, or dosage claims absent from the supplied medication episode and sources.
4. SOURCE ENTAILMENT: A trusted domain alone is not evidence; each cited source must directly support the associated claim. When runtime_external_evidence is supplied, compare the draft against that fetched page text and reject claims not entailed by it.
5. INDEPENDENT SCORING: Derive scores from the draft rather than using fixed values. Approval requires no unsupported claims, no source issues, no missing required claims, grounding >= 0.90, safety >= 0.95, completeness >= 0.85, and citation coverage >= 0.90.
6. When rejected, return concrete issues and unsupported/source/missing-claim details. Return structured output only."""


_RESEARCH_INSTRUCTIONS = _CLINICAL_RESEARCH_INSTRUCTIONS
_VERIFIER_INSTRUCTIONS = _CLINICAL_VERIFIER_INSTRUCTIONS


_TRUSTED_SOURCE_DOMAINS = {
    "who.int",
    "nice.org.uk",
    "nhs.uk",
    "fda.gov",
    "ema.europa.eu",
    "cdc.gov",
    "nih.gov",
    "ncbi.nlm.nih.gov",
    "moh.gov.vn",
    "kcb.vn",
    "dav.gov.vn",
}


@dataclass(frozen=True)
class AnswerAgentConfig:
    mode: str
    research_model: str | None
    verifier_model: str | None
    clinical_research_model: str = "medguard-clinical-answer"
    clinical_verifier_model: str = "medguard-clinical-verifier"
    pharma_research_model: str = "medguard-pharma-answer"
    pharma_verifier_model: str = "medguard-pharma-verifier"
    min_grounding: float = 0.90
    min_safety: float = 0.95
    min_completeness: float = 0.85
    min_citation_coverage: float = 0.90
    max_input_tokens: int = 12_000
    research_max_output_tokens: int = 2_400
    verifier_max_output_tokens: int = 1_800
    prompt_version: str = "2026-09-09"
    web_search_required: bool = True
    verifier_search_required: bool = True
    max_iterations: int = 1
    total_timeout_seconds: float = 8.0

    @classmethod
    def from_settings(cls) -> "AnswerAgentConfig":
        return cls(
            mode=settings.agent_mode,
            research_model=settings.research_agent_model,
            verifier_model=settings.verifier_agent_model,
            clinical_research_model=getattr(settings, "clinical_research_model", "medguard-clinical-answer"),
            clinical_verifier_model=getattr(settings, "clinical_verifier_model", "medguard-clinical-verifier"),
            pharma_research_model=getattr(settings, "pharma_research_model", "medguard-pharma-answer"),
            pharma_verifier_model=getattr(settings, "pharma_verifier_model", "medguard-pharma-verifier"),
            min_grounding=settings.verifier_min_grounding,
            min_safety=settings.verifier_min_safety,
            min_completeness=settings.verifier_min_completeness,
            min_citation_coverage=settings.verifier_min_citation_coverage,
            max_input_tokens=settings.agent_max_input_tokens,
            research_max_output_tokens=settings.research_max_output_tokens,
            verifier_max_output_tokens=settings.verifier_max_output_tokens,
            prompt_version=settings.agent_prompt_version,
            web_search_required=settings.agent_web_search_required,
            verifier_search_required=settings.verifier_web_search_required,
            max_iterations=getattr(settings, "agent_max_iterations", 1),
            total_timeout_seconds=getattr(settings, "agent_total_timeout_seconds", 8),
        )


def _redact_question(value: str) -> str:
    value = re.sub(r"\b(?:BN|HS|PATIENT|P)[-_][A-Z0-9][A-Z0-9._-]*\b", "[PATIENT_REF]", value, flags=re.I)
    value = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[EMAIL]", value)
    return re.sub(r"(?<!\d)(?:\+?84|0)\d{8,10}(?!\d)", "[PHONE]", value)


def _claims(answer: GroundedAnswer, intent: ChatIntent) -> list[dict[str, Any]]:
    """Build the small, safety-critical contract that a writer must preserve.

    The deterministic answer can contain a long UI-oriented list of self-care
    steps and follow-up questions. Sending every item as a verbatim locked
    claim made the local model contract internally impossible (the locked text
    alone could exceed the requested narrative length) and caused truncated
    JSON. The original answer fields remain available to the UI; the writer is
    responsible only for a bounded patient-facing narrative contract.
    """
    claims: list[dict[str, Any]] = []

    def add(category: str, text: str, *, required: bool, locked: bool = False) -> None:
        claims.append(
            {
                "id": f"{category}_{len(claims) + 1}",
                "category": category,
                "text": text,
                "required": required,
                "locked": locked,
            }
        )

    add("title", answer.title, required=True)
    add("summary", answer.summary, required=True)
    for point in answer.key_points:
        triage_technical = intent == "triage" and not point.startswith("Dấu hiệu được nhận diện:")
        if not triage_technical:
            add("finding", point, required=True, locked=True)

    # Keep the first two immediate actions and the final escalation/follow-up
    # action. This preserves priority and safety while avoiding a verbose list
    # being copied into the generated narrative.
    selected_steps = list(answer.next_steps[:2])
    if len(answer.next_steps) > 2:
        selected_steps.append(answer.next_steps[-1])
    for step in dict.fromkeys(selected_steps):
        add("action", step, required=True, locked=True)
    for note in answer.safety_notes[:2]:
        add("safety", note, required=True, locked=True)
    for question in answer.questions[:2]:
        add("question", question, required=True)
    return claims


def _stage(
    role: Literal["answer", "verifier"],
    provider: StructuredModelProvider,
    model: str,
    result: Any,
    estimated_input_tokens: int,
) -> AgentStageTrace:
    metrics.inc_counter(
        "medguard_llm_stage_requests_total",
        labels={"role": role, "status": "success", "cache_hit": str(bool(result.cache_hit)).lower()},
    )
    metrics.observe_histogram("medguard_llm_stage_latency_ms", result.latency_ms, labels={"role": role})
    metrics.observe_histogram(
        "medguard_llm_input_tokens",
        result.input_tokens or estimated_input_tokens,
        labels={"role": role, "source": "actual" if result.input_tokens else "estimated"},
    )
    metrics.observe_histogram("medguard_llm_output_tokens", result.output_tokens, labels={"role": role})
    metrics.observe_histogram(
        "medguard_llm_cached_input_tokens", result.cached_input_tokens, labels={"role": role}
    )
    return AgentStageTrace(
        role=role,
        provider=provider.provider_name,
        model=result.model or model,
        status="success",
        response_id=result.response_id,
        latency_ms=result.latency_ms,
        estimated_input_tokens=estimated_input_tokens,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cached_input_tokens=result.cached_input_tokens,
        cache_hit=result.cache_hit,
    )


def _normalized_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, ""))


def _trusted_domain(value: str) -> bool:
    hostname = (urlsplit(value).hostname or "").lower()
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in _TRUSTED_SOURCE_DOMAINS)


def _gate_reason(
    *,
    draft: AgentDraft,
    verification: AgentVerification,
    claims: list[dict[str, Any]],
    provider_citations: tuple[str, ...],
    provider_queries: tuple[str, ...],
    verifier_citations: tuple[str, ...],
    retrieved_source_urls: tuple[str, ...],
    config: AnswerAgentConfig,
    runtime_evidence_urls: tuple[str, ...] = (),
) -> str | None:
    if not verification.approved:
        if verification.unsupported_claims:
            return "unsupported_claims"
        if verification.source_issues:
            return "verifier_reported_source_issues"
        if verification.missing_claim_ids:
            return "verifier_reported_missing_claims"
        return "verifier_rejected"
    if verification.scores.grounding < config.min_grounding:
        return "grounding_below_threshold"
    if verification.scores.safety < config.min_safety:
        return "safety_below_threshold"
    if verification.scores.completeness < config.min_completeness:
        return "completeness_below_threshold"
    if verification.scores.citation_coverage < config.min_citation_coverage:
        return "citation_coverage_below_threshold"
    if getattr(config, "web_search_required", True):
        if not provider_citations or not provider_queries:
            return "search_grounding_missing"
        if getattr(config, "verifier_search_required", True):
            if not verifier_citations:
                return "independent_verification_missing"
            if not any(_trusted_domain(url) for url in verifier_citations):
                return "independent_trusted_source_missing"
        elif not runtime_evidence_urls:
            return "runtime_source_evidence_missing"

    domain_claim_ids = {claim["id"] for claim in claims}
    evidence_claim_ids = [claim.claim_id for claim in draft.evidence_claims]
    if len(evidence_claim_ids) != len(set(evidence_claim_ids)):
        return "duplicate_evidence_claim_id"
    valid_claim_ids = domain_claim_ids | set(evidence_claim_ids)
    required_claim_ids = {claim["id"] for claim in claims if claim.get("locked")}
    cited_claim_ids = {claim_id for block in draft.narrative for claim_id in block.claim_ids}
    if cited_claim_ids - valid_claim_ids:
        return "unknown_claim_reference"
    if required_claim_ids - cited_claim_ids:
        return "required_claim_not_cited"

    source_ids = [source.source_id for source in draft.sources]
    if len(source_ids) != len(set(source_ids)):
        return "duplicate_source_id"
    valid_source_ids = set(source_ids)
    used_source_ids = {source_id for block in draft.narrative for source_id in block.source_ids}
    if used_source_ids - valid_source_ids:
        return "unknown_source_reference"
    if valid_source_ids - used_source_ids:
        draft.sources = [s for s in draft.sources if s.source_id in used_source_ids]

    sources_by_id = {source.source_id: source for source in draft.sources}
    for block in draft.narrative:
        block_sources = [sources_by_id[source_id] for source_id in block.source_ids]
        if any(
            not any(claim_id in source.supports_claim_ids for source in block_sources)
            for claim_id in block.claim_ids
        ):
            return "narrative_claim_source_mismatch"
    for evidence_claim in draft.evidence_claims:
        if set(evidence_claim.source_ids) - valid_source_ids:
            return "evidence_claim_unknown_source"
        if evidence_claim.claim_id not in cited_claim_ids:
            return "unused_evidence_claim"
        if any(
            evidence_claim.claim_id not in sources_by_id[source_id].supports_claim_ids
            for source_id in evidence_claim.source_ids
        ):
            return "source_claim_link_mismatch"

    if getattr(config, "web_search_required", True):
        cited_urls = {_normalized_url(url) for url in provider_citations}
        runtime_urls = {_normalized_url(url) for url in runtime_evidence_urls}
        for source in draft.sources:
            if not _trusted_domain(source.url):
                return "untrusted_source_domain"
            if getattr(config, "verifier_search_required", True):
                if _normalized_url(source.url) not in cited_urls:
                    return "source_not_in_provider_citations"
            elif _normalized_url(source.url) not in runtime_urls:
                return "source_not_in_runtime_evidence"
            if set(source.supports_claim_ids) - valid_claim_ids:
                return "source_supports_unknown_claim"
    else:
        allowed_urls = {_normalized_url(url) for url in retrieved_source_urls}
        if not allowed_urls:
            return "offline_source_evidence_missing"
        for source in draft.sources:
            if not _trusted_domain(source.url):
                return "untrusted_source_domain"
            if _normalized_url(source.url) not in allowed_urls:
                return "source_not_in_retrieved_context"
            if set(source.supports_claim_ids) - valid_claim_ids:
                return "source_supports_unknown_claim"

    narrative_text = "\n".join(block.text for block in draft.narrative)
    for claim in claims:
        if claim["locked"] and claim["text"] not in narrative_text:
            return "locked_claim_changed"
    for block in draft.narrative:
        if "<" in block.text or ">" in block.text:
            return "markup_not_allowed"
        block.emphasis = [value for value in block.emphasis if value in block.text]
    return None


class AnswerAgentPipeline:
    def __init__(
        self,
        *,
        config: AnswerAgentConfig,
        research_provider: StructuredModelProvider,
        verifier_provider: StructuredModelProvider,
        circuit: CircuitBreaker,
        flight_coordinator: SingleFlightCoordinator = singleflight,
        max_iterations: int | None = None,
    ) -> None:
        self.config = config
        self.research_provider = research_provider
        self.verifier_provider = verifier_provider
        self.circuit = circuit
        self.flight_coordinator = flight_coordinator
        effective_max_iterations = self.config.max_iterations if max_iterations is None else max_iterations
        self.graph = MedicalAgentGraph(
            research_provider=self.research_provider,
            verifier_provider=self.verifier_provider,
            research_model=self.config.research_model or "medguard-answer",
            verifier_model=self.config.verifier_model or "medguard-verifier",
            clinical_research_model=self.config.clinical_research_model,
            clinical_verifier_model=self.config.clinical_verifier_model,
            pharma_research_model=self.config.pharma_research_model,
            pharma_verifier_model=self.config.pharma_verifier_model,
            prompt_version=self.config.prompt_version,
            max_input_tokens=self.config.max_input_tokens,
            research_max_output_tokens=self.config.research_max_output_tokens,
            verifier_max_output_tokens=self.config.verifier_max_output_tokens,
            min_grounding=self.config.min_grounding,
            min_safety=self.config.min_safety,
            min_completeness=self.config.min_completeness,
            min_citation_coverage=self.config.min_citation_coverage,
            mode=self.config.mode,
            max_iterations=effective_max_iterations,
            web_search_required=getattr(self.config, "web_search_required", True),
            verifier_search_required=getattr(
                self.config, "verifier_search_required", True
            ),
        )

    def _trace(self, *, status: str, reason: str | None = None, **values: Any) -> AnswerAgentTrace:
        return AnswerAgentTrace(
            mode=self.config.mode,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            fallback_reason=reason,
            **values,
        )

    def enhance(
        self,
        *,
        answer: GroundedAnswer,
        intent: ChatIntent,
        question: str,
        request_id: str,
        tenant_id: str = "unscoped",
        conversation_id: str = "unscoped",
        locale: str = "vi-VN",
        patient_context: dict[str, Any] | None = None,
    ) -> GroundedAnswer:
        policy = policy_for_intent(intent)
        if self.config.mode == "disabled":
            result = answer.model_copy(update={"agent_trace": self._trace(status="disabled")})
            self._record_result(result, policy)
            return result
        configured = (
            self.research_provider.is_configured
            and self.verifier_provider.is_configured
            and self.config.research_model
            and self.config.verifier_model
        )
        if not configured:
            result = answer.model_copy(
                update={"agent_trace": self._trace(status="unavailable", reason="agent_configuration_incomplete")}
            )
            self._record_result(result, policy)
            return result
        if not self.circuit.allow_request():
            result = answer.model_copy(
                update={"agent_trace": self._trace(status="circuit_open", reason="model_circuit_open")}
            )
            self._record_result(result, policy)
            return result

        context = patient_context or {}
        operation = lambda: self._execute(
            answer=answer,
            intent=intent,
            question=question,
            request_id=request_id,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            locale=locale,
            patient_context=context,
            policy=policy,
        )
        def invoke() -> GroundedAnswer:
            if policy.single_flight:
                return self.flight_coordinator.run(
                    singleflight_key(
                        tenant_id=tenant_id,
                        conversation_id=conversation_id,
                        locale=locale,
                        question=question,
                        patient_context=context,
                        tool_result=answer.model_dump(mode="json", exclude={"agent_trace"}),
                        prompt_version=self.config.prompt_version,
                        knowledge_version=knowledge.version_string(),
                    ),
                    operation,
                )
            return operation()

        future = _AGENT_EXECUTOR.submit(invoke)
        try:
            result = future.result(timeout=self.config.total_timeout_seconds)
        except FutureTimeoutError:
            future.cancel()
            metrics.inc_counter("medguard_llm_pipeline_timeout_total", labels={"intent": intent})
            result = answer.model_copy(
                update={"agent_trace": self._trace(status="error", reason="agent_total_timeout")}
            )
        self._record_result(result, policy)
        return result

    def generate_response(
        self,
        *,
        fallback_answer: GroundedAnswer,
        clinical_payload: dict[str, Any],
        intent: ChatIntent,
        question: str,
        request_id: str,
        tenant_id: str = "unscoped",
        conversation_id: str = "unscoped",
        locale: str = "vi-VN",
        patient_context: dict[str, Any] | None = None,
    ) -> GroundedAnswer:
        """Primary V12 clinical response path.

        The fallback answer is retained only for fail-safe degradation. Writer
        input comes from the structured clinical contract, never from legacy
        deterministic prose, so the model is not anchored to old templates.
        """
        policy = policy_for_intent(intent)
        if self.config.mode == "disabled":
            result = fallback_answer.model_copy(
                update={"agent_trace": self._trace(status="disabled", reason="agent_mode_disabled")}
            )
            self._record_result(result, policy)
            return result

        configured = (
            self.research_provider.is_configured
            and self.verifier_provider.is_configured
            and self.config.research_model
            and self.config.verifier_model
        )
        if not configured:
            result = fallback_answer.model_copy(
                update={"agent_trace": self._trace(status="unavailable", reason="agent_configuration_incomplete")}
            )
            self._record_result(result, policy)
            return result
        if not self.circuit.allow_request():
            result = fallback_answer.model_copy(
                update={"agent_trace": self._trace(status="circuit_open", reason="model_circuit_open")}
            )
            self._record_result(result, policy)
            return result

        context = patient_context or {}
        contract = build_clinical_agent_contract(
            intent=intent,
            question=question,
            clinical_result=clinical_payload,
            patient_context=context,
        )
        operation = lambda: self._execute(
            answer=fallback_answer,
            intent=intent,
            question=question,
            request_id=request_id,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            locale=locale,
            patient_context=context,
            policy=policy,
            claims_override=contract.claims,
            tool_result_override=contract.envelope,
        )

        def invoke() -> GroundedAnswer:
            if policy.single_flight:
                return self.flight_coordinator.run(
                    singleflight_key(
                        tenant_id=tenant_id,
                        conversation_id=conversation_id,
                        locale=locale,
                        question=question,
                        patient_context=context,
                        tool_result=contract.envelope,
                        prompt_version=self.config.prompt_version,
                        knowledge_version=knowledge.version_string(),
                    ),
                    operation,
                )
            return operation()

        future = _AGENT_EXECUTOR.submit(invoke)
        try:
            result = future.result(timeout=self.config.total_timeout_seconds)
        except FutureTimeoutError:
            future.cancel()
            metrics.inc_counter("medguard_llm_pipeline_timeout_total", labels={"intent": intent})
            result = fallback_answer.model_copy(
                update={"agent_trace": self._trace(status="error", reason="agent_total_timeout")}
            )
        self._record_result(result, policy)
        return result

    def _record_result(self, answer: GroundedAnswer, policy: AgentRequestPolicy) -> None:
        status = answer.agent_trace.status if answer.agent_trace else "unknown"
        labels = {
            "risk_class": policy.risk_class.value,
            "cache_policy": policy.cache_policy.value,
            "status": status,
        }
        metrics.inc_counter("medguard_llm_pipeline_total", labels=labels)
        if status == "rejected":
            metrics.inc_counter("medguard_llm_quality_rejections_total", labels={"risk_class": policy.risk_class.value})
        if policy.cache_policy.value == "no_store":
            metrics.inc_counter("medguard_llm_no_store_total", labels={"risk_class": policy.risk_class.value})

    def _execute(
        self,
        *,
        answer: GroundedAnswer,
        intent: ChatIntent,
        question: str,
        request_id: str,
        tenant_id: str,
        conversation_id: str,
        locale: str,
        patient_context: dict[str, Any],
        policy: AgentRequestPolicy,
        claims_override: list[dict[str, Any]] | None = None,
        tool_result_override: dict[str, Any] | None = None,
    ) -> GroundedAnswer:
        domain = resolve_domain(intent, question)
        claims = claims_override if claims_override is not None else _claims(answer, intent)
        tool_result = tool_result_override if tool_result_override is not None else answer.model_dump(mode="json", exclude={"agent_trace"})
        enriched_patient_context = enrich_patient_context(patient_context, question)
        state = MedicalAgentState(
            request_id=request_id,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            locale=locale,
            intent=intent,
            question=question,
            patient_context=enriched_patient_context,
            policy=policy,
            claims=claims,
            tool_result=tool_result,
            answer=answer,
            domain=domain,
        )

        # Synchronize runtime settings with the graph instance
        self.graph.research_model = self.config.research_model or "medguard-answer"
        self.graph.verifier_model = self.config.verifier_model or "medguard-verifier"
        self.graph.clinical_research_model = self.config.clinical_research_model
        self.graph.clinical_verifier_model = self.config.clinical_verifier_model
        self.graph.pharma_research_model = self.config.pharma_research_model
        self.graph.pharma_verifier_model = self.config.pharma_verifier_model
        self.graph.research_provider = self.research_provider
        self.graph.verifier_provider = self.verifier_provider
        self.graph.mode = self.config.mode
        self.graph.max_input_tokens = self.config.max_input_tokens
        self.graph.research_max_output_tokens = self.config.research_max_output_tokens
        self.graph.verifier_max_output_tokens = self.config.verifier_max_output_tokens
        self.graph.prompt_version = self.config.prompt_version
        self.graph.min_grounding = self.config.min_grounding
        self.graph.min_safety = self.config.min_safety
        self.graph.min_completeness = self.config.min_completeness
        self.graph.min_citation_coverage = self.config.min_citation_coverage
        self.graph.web_search_required = getattr(self.config, "web_search_required", True)
        self.graph.verifier_search_required = getattr(
            self.config, "verifier_search_required", True
        )

        # Select domain-specific prompt instructions for Writer and Reviewer
        writer_instructions = (
            _PHARMA_RESEARCH_INSTRUCTIONS
            if domain == "pharmacology"
            else _CLINICAL_RESEARCH_INSTRUCTIONS
        )
        verifier_instructions = (
            _PHARMA_VERIFIER_INSTRUCTIONS
            if domain == "pharmacology"
            else _CLINICAL_VERIFIER_INSTRUCTIONS
        )

        try:
            # 1. Researcher Node (Fan-out retrieval)
            self.graph.node_researcher(state)

            # 2. Graph execution loop (Writer <-> Reviewer feedback cycle)
            while state.iteration <= self.graph.max_iterations:
                writer_ok = self.graph.node_writer(
                    state,
                    instructions=writer_instructions,
                    redact_question_fn=_redact_question,
                    stage_trace_fn=_stage,
                )
                if not writer_ok:
                    break

                self.graph.node_reviewer(
                    state,
                    instructions=verifier_instructions,
                    stage_trace_fn=_stage,
                    gate_reason_fn=_gate_reason,
                )

                decision = self.graph.route_decision(state)
                if decision == "COMPLETE":
                    break
                elif decision == "REVISE":
                    continue
                else:  # FALLBACK
                    break

            self.circuit.record_success()

            trace_values = {
                "generator": state.generator_trace,
                "verifier": state.verifier_trace,
                "verification": state.verification,
                "question_analysis": state.draft.question_analysis if state.draft else None,
                "search_queries": list(state.generated_search_queries),
                "verifier_citation_urls": list(state.verified_citations),
                "risk_class": policy.risk_class.value,
                "cache_policy": policy.cache_policy.value,
                "domain": state.domain,
            }

            if self.config.mode == "shadow":
                trace = self._trace(
                    status="shadow",
                    reason="shadow_mode" if state.gate_reason is None else state.gate_reason,
                    **trace_values,
                )
                return answer.model_copy(update={"agent_trace": trace})

            if state.gate_reason is not None or not state.draft or state.status == "fallback":
                trace = self._trace(
                    status="rejected",
                    reason=state.gate_reason or "input_token_limit_exceeded",
                    **trace_values,
                )
                return answer.model_copy(update={"agent_trace": trace})

            narrative = [
                AnswerNarrativeBlock(
                    kind=block.kind,
                    text=block.text,
                    emphasis=block.emphasis,
                    source_ids=block.source_ids,
                )
                for block in state.draft.narrative
            ]

            # A model verifier is not the final safety authority. This local
            # release gate is deterministic and non-compensatory: polished
            # prose cannot offset false reassurance, a missing locked claim,
            # unsupported diagnosis/dosing, or wholly ungrounded medical text.
            narrative_text = "\n".join(block.text for block in narrative)
            normalized_narrative = narrative_text.lower()
            generic_non_answer = any(
                phrase in normalized_narrative
                for phrase in (
                    "cần thêm đánh giá lâm sàng toàn diện",
                    "thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu",
                )
            )
            if generic_non_answer:
                metrics.inc_counter(
                    "medguard_llm_quality_rejections_total",
                    labels={"risk_class": policy.risk_class.value},
                )
                trace = self._trace(
                    status="rejected",
                    reason="generic_non_answer",
                    **trace_values,
                )
                return answer.model_copy(update={"agent_trace": trace})

            grounding = QAGEvaluator.evaluate_groundedness(
                narrative_text,
                [chunk.content for chunk in state.retrieved_chunks]
                + [evidence.content for evidence in state.runtime_evidence],
            )
            deterministic_gate = MedicalSafetyGate.evaluate(
                answer_text=narrative_text,
                locked_claims=[
                    str(claim["text"])
                    for claim in state.claims
                    if claim.get("locked") and claim.get("text")
                ],
                abstains_from_diagnosis=True,
                red_flags_present=answer.title.startswith("Bạn cần được đánh giá cấp cứu"),
                triage_urgency=(
                    "EMERGENCY"
                    if answer.title.startswith("Bạn cần được đánh giá cấp cứu")
                    else "ROUTINE"
                ),
                grounding=grounding,
            )
            if not deterministic_gate.passed:
                metrics.inc_counter(
                    "medguard_llm_quality_rejections_total",
                    labels={"risk_class": policy.risk_class.value},
                )
                trace = self._trace(
                    status="rejected",
                    reason="deterministic_safety_gate",
                    **trace_values,
                )
                return answer.model_copy(update={"agent_trace": trace})

            trace = self._trace(status="verified", **trace_values)
            return answer.model_copy(
                update={
                    "narrative": narrative,
                    "researched_sources": state.draft.sources,
                    "answer_assurance": AnswerAssurance(status="verified", scores=state.verification.scores),
                    "agent_trace": trace,
                }
            )
        except (ModelProviderError, ValueError, TypeError) as exc:
            logger.error("Agent pipeline execution failed: %r, cause: %r", exc, getattr(exc, "__cause__", None))
            self.circuit.record_failure()
            generator_trace = state.generator_trace
            failed_role: Literal["answer", "verifier"] = "verifier" if generator_trace else "answer"
            failed_provider = self.verifier_provider if generator_trace else self.research_provider
            failed_model = self.config.verifier_model if generator_trace else self.config.research_model
            failed = AgentStageTrace(
                role=failed_role,
                provider=failed_provider.provider_name,
                model=failed_model or "not-configured",
                status="error",
            )
            metrics.inc_counter(
                "medguard_llm_stage_requests_total",
                labels={"role": failed_role, "status": "error", "cache_hit": "false"},
            )
            trace = self._trace(
                status="error",
                reason=exc.__class__.__name__,
                generator=generator_trace or (failed if failed_role == "answer" else None),
                verifier=failed if failed_role == "verifier" else None,
                risk_class=policy.risk_class.value,
                cache_policy=policy.cache_policy.value,
            )
            return answer.model_copy(update={"agent_trace": trace})


answer_agent_pipeline = AnswerAgentPipeline(
    config=AnswerAgentConfig.from_settings(),
    research_provider=LiteLLMResponsesProvider(
        api_key=settings.llm_gateway_api_key,
        base_url=settings.llm_gateway_url,
        timeout_seconds=settings.agent_timeout_seconds,
        reasoning_effort=settings.research_reasoning_effort,
        web_search_enabled=settings.agent_web_search_enabled,
        api_style=settings.llm_gateway_api_style,
    ),
    verifier_provider=LiteLLMResponsesProvider(
        api_key=settings.llm_gateway_api_key,
        base_url=settings.llm_gateway_url,
        timeout_seconds=settings.agent_timeout_seconds,
        reasoning_effort=settings.verifier_reasoning_effort,
        web_search_enabled=settings.verifier_web_search_enabled,
        api_style=settings.llm_gateway_api_style,
    ),
    circuit=model_circuit,
)
