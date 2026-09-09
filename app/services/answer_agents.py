from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

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
from app.services.knowledge_retriever import knowledge_retriever
from app.services.llm_control_plane import (
    AgentRequestPolicy,
    SingleFlightCoordinator,
    gateway_controls,
    policy_for_intent,
    singleflight,
    singleflight_key,
)


_RESEARCH_INSTRUCTIONS = """You are MedGuard's Question and Evidence Agent.
Analyze the bounded Vietnamese clinical episode, search the web, and write a concise professional answer.
Use only supplied domain claims for patient-specific findings, urgency, actions, and safety advice.
Prefer current primary sources from health authorities, regulators, clinical guidelines, or peer-reviewed literature.
Do not use forums, commercial health blogs, social media, or anonymous summaries.
Do not diagnose, prescribe, invent causes, add doses, weaken urgency, or claim certainty.
Write 3 to 5 natural paragraphs in the style of a careful clinical conversation, not a form or report.
Lead with the practical assessment, then urgent warning signs, bounded self-care, and focused follow-up questions.
Do not add a greeting, role-play as a doctor, repeat headings, expose workflow stages, or mention model/provider names.
Every block must cite both supporting claim_ids and source_ids. Every source URL must come from Google Search.
New general evidence must be placed in evidence_claims with ext_ IDs and remain non-diagnostic.
Claims marked locked=true must appear verbatim. Emphasis must be an exact substring. Return structured output only."""


_VERIFIER_INSTRUCTIONS = """You are MedGuard's independent medical-answer credibility verifier.
Evaluate the draft against the immutable domain claims and the supplied Google citation URLs.
Use your own web search to independently corroborate the medical claims. Prefer only the trusted domains supplied.
Reject unsupported medical text, fabricated or weak sources, changed urgency, missing required or locked claims,
diagnosis claims, unsafe medication advice, false certainty, citation mismatch, or omissions affecting patient action.
Score grounding, safety, completeness, clarity, and citation coverage from 0 to 1.
Approval requires no unsupported claims, no source issues, and no missing claim IDs. Return structured output only."""


_TRUSTED_SOURCE_DOMAINS = {
    "who.int",
    "nice.org.uk",
    "nhs.uk",
    "fda.gov",
    "ema.europa.eu",
    "cdc.gov",
    "nih.gov",
    "ncbi.nlm.nih.gov",
    "dailymed.nlm.nih.gov",
    "moh.gov.vn",
    "dav.gov.vn",
    "cochranelibrary.com",
}


@dataclass(frozen=True)
class AnswerAgentConfig:
    mode: str
    research_model: str | None
    verifier_model: str | None
    min_grounding: float
    min_safety: float
    min_completeness: float
    min_citation_coverage: float
    max_input_tokens: int = 12_000
    research_max_output_tokens: int = 2_400
    verifier_max_output_tokens: int = 1_800
    prompt_version: str = "2026-09-09"

    @classmethod
    def from_settings(cls) -> "AnswerAgentConfig":
        return cls(
            mode=settings.agent_mode,
            research_model=settings.research_agent_model,
            verifier_model=settings.verifier_agent_model,
            min_grounding=settings.verifier_min_grounding,
            min_safety=settings.verifier_min_safety,
            min_completeness=settings.verifier_min_completeness,
            min_citation_coverage=settings.verifier_min_citation_coverage,
            max_input_tokens=settings.agent_max_input_tokens,
            research_max_output_tokens=settings.research_max_output_tokens,
            verifier_max_output_tokens=settings.verifier_max_output_tokens,
            prompt_version=settings.agent_prompt_version,
        )


def _redact_question(value: str) -> str:
    value = re.sub(r"\b(?:BN|HS|PATIENT|P)[-_][A-Z0-9][A-Z0-9._-]*\b", "[PATIENT_REF]", value, flags=re.I)
    value = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[EMAIL]", value)
    return re.sub(r"(?<!\d)(?:\+?84|0)\d{8,10}(?!\d)", "[PHONE]", value)


def _claims(answer: GroundedAnswer, intent: ChatIntent) -> list[dict[str, Any]]:
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
        add("finding", point, required=not triage_technical, locked=not triage_technical)
    for step in answer.next_steps:
        add("action", step, required=True, locked=True)
    for note in answer.safety_notes:
        add("safety", note, required=True, locked=True)
    for question in answer.questions:
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
    config: AnswerAgentConfig,
) -> str | None:
    if not verification.approved:
        return "verifier_rejected"
    if verification.unsupported_claims:
        return "unsupported_claims"
    if verification.source_issues:
        return "verifier_reported_source_issues"
    if verification.missing_claim_ids:
        return "verifier_reported_missing_claims"
    if verification.scores.grounding < config.min_grounding:
        return "grounding_below_threshold"
    if verification.scores.safety < config.min_safety:
        return "safety_below_threshold"
    if verification.scores.completeness < config.min_completeness:
        return "completeness_below_threshold"
    if verification.scores.citation_coverage < config.min_citation_coverage:
        return "citation_coverage_below_threshold"
    if not provider_citations or not provider_queries:
        return "search_grounding_missing"
    if not verifier_citations:
        return "independent_verification_missing"
    if not any(_trusted_domain(url) for url in verifier_citations):
        return "independent_trusted_source_missing"

    domain_claim_ids = {claim["id"] for claim in claims}
    evidence_claim_ids = [claim.claim_id for claim in draft.evidence_claims]
    if len(evidence_claim_ids) != len(set(evidence_claim_ids)):
        return "duplicate_evidence_claim_id"
    valid_claim_ids = domain_claim_ids | set(evidence_claim_ids)
    required_claim_ids = {claim["id"] for claim in claims if claim["required"]}
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
        return "unused_source"

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

    cited_urls = {_normalized_url(url) for url in provider_citations}
    for source in draft.sources:
        if not _trusted_domain(source.url):
            return "untrusted_source_domain"
        if _normalized_url(source.url) not in cited_urls:
            return "source_not_in_provider_citations"
        if set(source.supports_claim_ids) - valid_claim_ids:
            return "source_supports_unknown_claim"

    narrative_text = "\n".join(block.text for block in draft.narrative)
    for evidence_claim in draft.evidence_claims:
        if evidence_claim.text not in narrative_text:
            return "evidence_claim_changed"
    for claim in claims:
        if claim["locked"] and claim["text"] not in narrative_text:
            return "locked_claim_changed"
    for block in draft.narrative:
        if "<" in block.text or ">" in block.text:
            return "markup_not_allowed"
        if any(value not in block.text for value in block.emphasis):
            return "invalid_emphasis"
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
        max_iterations: int = 2,
    ) -> None:
        self.config = config
        self.research_provider = research_provider
        self.verifier_provider = verifier_provider
        self.circuit = circuit
        self.flight_coordinator = flight_coordinator
        self.graph = MedicalAgentGraph(
            research_provider=self.research_provider,
            verifier_provider=self.verifier_provider,
            research_model=self.config.research_model or "medguard-answer",
            verifier_model=self.config.verifier_model or "medguard-verifier",
            prompt_version=self.config.prompt_version,
            max_input_tokens=self.config.max_input_tokens,
            research_max_output_tokens=self.config.research_max_output_tokens,
            verifier_max_output_tokens=self.config.verifier_max_output_tokens,
            min_grounding=self.config.min_grounding,
            min_safety=self.config.min_safety,
            min_completeness=self.config.min_completeness,
            min_citation_coverage=self.config.min_citation_coverage,
            mode=self.config.mode,
            max_iterations=max_iterations,
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
        if policy.single_flight:
            result = self.flight_coordinator.run(
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
        else:
            result = operation()
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
    ) -> GroundedAnswer:
        claims = _claims(answer, intent)
        tool_result = answer.model_dump(mode="json", exclude={"agent_trace"})
        state = MedicalAgentState(
            request_id=request_id,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            locale=locale,
            intent=intent,
            question=question,
            patient_context=patient_context,
            policy=policy,
            claims=claims,
            tool_result=tool_result,
            answer=answer,
        )

        # Synchronize runtime settings with the graph instance
        self.graph.research_model = self.config.research_model or "medguard-answer"
        self.graph.verifier_model = self.config.verifier_model or "medguard-verifier"
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

        try:
            # 1. Researcher Node (Fan-out retrieval)
            self.graph.node_researcher(state)

            # 2. Graph execution loop (Writer <-> Reviewer feedback cycle)
            while state.iteration <= self.graph.max_iterations:
                writer_ok = self.graph.node_writer(
                    state,
                    instructions=_RESEARCH_INSTRUCTIONS,
                    redact_question_fn=_redact_question,
                    stage_trace_fn=_stage,
                )
                if not writer_ok:
                    break

                self.graph.node_reviewer(
                    state,
                    instructions=_VERIFIER_INSTRUCTIONS,
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
            self.circuit.record_failure()
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
    ),
    verifier_provider=LiteLLMResponsesProvider(
        api_key=settings.llm_gateway_api_key,
        base_url=settings.llm_gateway_url,
        timeout_seconds=settings.agent_timeout_seconds,
        reasoning_effort=settings.verifier_reasoning_effort,
    ),
    circuit=model_circuit,
)
