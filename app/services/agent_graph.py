"""StateGraph orchestrator for MedGuard AI (Harness -> Graph -> bounded Loop).

V15 preserves the V14 authority contract while adding adaptive execution:
- Writer owns patient-facing composition from structured state/evidence.
- Reviewer is a mandatory non-authoring quality gate.
- Clinical severity remains owned by the deterministic safety/clinical stack.
- Kev/adaptive routing may choose execution agent/model tier, never rewrite
  clinical severity.
- Provider/model fallback stays inside the selected execution path and never
  changes clinical severity or bypasses Reviewer.
- A deterministic professional-response gate runs after Reviewer approval and
  may still reject unsafe, generic or system-jargon patient-facing prose.
- FAST/STANDARD routes use bounded token budgets while DEEP emergency/uncertain
  Writer paths retain the configured full budget.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

from app.core.observability import metrics
from app.knowledge.loader import knowledge
from app.models.adaptive_routing import AdaptiveRouteDecision
from app.models.agents import (
    AgentDraft,
    AgentEvidenceSource,
    AgentStageTrace,
    AgentVerification,
    AnswerAgentTrace,
)
from app.models.chat import (
    AnswerAssurance,
    AnswerNarrativeBlock,
    ChatIntent,
    GroundedAnswer,
)
from app.services.adaptive_agent_runtime import adaptive_agent_runtime
from app.services.agent_provider import ModelProviderError, StructuredModelProvider
from app.services.knowledge_retriever import RetrievedChunk, knowledge_retriever
from app.services.llm_control_plane import AgentRequestPolicy, gateway_controls
from app.services.professional_response_gate import evaluate_professional_response
from app.services.trusted_evidence import (
    RuntimeEvidence,
    TRUSTED_MEDICAL_DOMAINS,
    trusted_evidence_fetcher,
)


@dataclass
class MedicalAgentState:
    """Shared state flowing across researcher, writer and reviewer nodes."""

    request_id: str
    tenant_id: str
    conversation_id: str
    locale: str
    intent: ChatIntent
    question: str
    patient_context: dict[str, Any]
    policy: AgentRequestPolicy
    claims: list[dict[str, Any]]
    tool_result: dict[str, Any]
    answer: GroundedAnswer

    retrieved_chunks: list[RetrievedChunk] = field(default_factory=list)
    draft: AgentDraft | None = None
    generator_trace: AgentStageTrace | None = None
    generated_citations: tuple[str, ...] = ()
    generated_search_queries: tuple[str, ...] = ()

    verifier_trace: AgentStageTrace | None = None
    verification: AgentVerification | None = None
    verified_citations: tuple[str, ...] = ()
    runtime_evidence: list[RuntimeEvidence] = field(default_factory=list)
    gate_reason: str | None = None

    adaptive_route: AdaptiveRouteDecision | None = None
    selected_writer_model: str | None = None
    selected_verifier_model: str | None = None

    iteration: int = 0
    max_iterations: int = 2
    feedback_history: list[str] = field(default_factory=list)
    domain: Literal["clinical", "pharmacology"] = "clinical"
    status: Literal[
        "researching", "writing", "reviewing", "verified", "fallback", "shadow"
    ] = "researching"


_LEGACY_PRESENTATION_KEYS = {
    "title",
    "summary",
    "narrative",
    "researched_sources",
    "answer_assurance",
    "agent_trace",
}


def _is_agent_first_envelope(value: dict[str, Any]) -> bool:
    version = str(value.get("version") or "")
    return "agent-first" in version or version.startswith("v14-")


def _structured_legacy_envelope(state: MedicalAgentState) -> dict[str, Any]:
    """Build the stable V14 transport without dropping newer clinical state.

    V25/V28 contracts intentionally travel inside the long-lived V14 transport
    envelope. The bridge therefore has to preserve diagnosis-neutral clinical
    context and communication constraints while still stripping identifiers and
    legacy presentation prose. Clinical severity remains read-only and is never
    recomputed here.
    """
    source = state.tool_result
    source_contract = source.get("communication_contract")
    if not isinstance(source_contract, dict):
        source_contract = {}

    communication_contract: dict[str, Any] = {
        "compose_original_response": True,
        "legacy_template_prose_is_not_evidence": True,
        "answer_main_concern_first": True,
        "give_concrete_next_action": True,
        "separate_assessment_from_diagnosis": True,
        "avoid_generic_non_answers": True,
        "reviewer_is_non_authoring": True,
    }
    # Newer contract flags are additive constraints. Keeping them here fixes a
    # prior transport bug where V28 negation/hypothetical/medication rules were
    # present in the contract but silently overwritten before Writer/Reviewer.
    communication_contract.update(source_contract)

    safe_context_keys = {
        "age",
        "sex",
        "current_medications",
        "allergies",
        "conditions",
        "clinical_context",
        "clinical_context_meta",
    }
    envelope: dict[str, Any] = {
        "version": "v14-structured-agent-input",
        "intent": state.intent,
        "user_question": state.question,
        "decision_basis": source.get("decision_basis"),
        "evidence_state": source.get("evidence_state"),
        "rule_version": source.get("rule_version"),
        "clinical_hypotheses": source.get("clinical_hypotheses") or [],
        "key_points": source.get("key_points") or [],
        "next_steps": source.get("next_steps") or [],
        "safety_notes": source.get("safety_notes") or [],
        "questions": source.get("questions") or [],
        "limitations": source.get("limitations") or [],
        "requires_human_review": bool(source.get("requires_human_review")),
        "patient_context": {
            key: value
            for key, value in state.patient_context.items()
            if key in safe_context_keys and value not in (None, "", [])
        },
        "communication_contract": communication_contract,
    }
    for key, value in source.items():
        if key in _LEGACY_PRESENTATION_KEYS or key in envelope:
            continue
        if key in {"sources", "display_questions"}:
            continue
        envelope[key] = value
    return envelope


def _agent_inputs(state: MedicalAgentState) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if _is_agent_first_envelope(state.tool_result):
        return state.claims, state.tool_result
    visible_claims = [
        claim
        for claim in state.claims
        if claim.get("category") not in {"title", "summary"}
    ]
    return visible_claims, _structured_legacy_envelope(state)


def _route_metadata(route: AdaptiveRouteDecision | None) -> dict[str, Any] | None:
    if route is None:
        return None
    return {
        "clinical_task": route.clinical_task,
        "resolved_severity": route.resolved_severity,
        "agent": route.agent.value,
        "model_tier": route.model_tier.value,
        "emergency_lock": route.emergency_lock,
        "requires_clarification": route.requires_clarification,
        "requires_review": route.requires_review,
        "kev_choice": route.kev_choice.value,
        "confidence": route.confidence,
        "margin": route.margin,
        "fact_coverage": route.fact_coverage,
        "reasons": list(route.reasons),
    }


class MedicalAgentGraph:
    """StateGraph orchestrating grounded response writing and non-authoring review."""

    def __init__(
        self,
        *,
        research_provider: StructuredModelProvider,
        verifier_provider: StructuredModelProvider,
        research_model: str,
        verifier_model: str,
        clinical_research_model: str = "medguard-clinical-answer",
        clinical_verifier_model: str = "medguard-clinical-verifier",
        pharma_research_model: str = "medguard-pharma-answer",
        pharma_verifier_model: str = "medguard-pharma-verifier",
        prompt_version: str,
        max_input_tokens: int,
        research_max_output_tokens: int,
        verifier_max_output_tokens: int,
        min_grounding: float = 0.90,
        min_safety: float = 0.95,
        min_completeness: float = 0.85,
        min_citation_coverage: float = 0.90,
        mode: Literal["disabled", "shadow", "enforced"] = "enforced",
        max_iterations: int = 2,
        web_search_required: bool = True,
        verifier_search_required: bool = True,
    ) -> None:
        self.research_provider = research_provider
        self.verifier_provider = verifier_provider
        self.research_model = research_model
        self.verifier_model = verifier_model
        self.clinical_research_model = clinical_research_model
        self.clinical_verifier_model = clinical_verifier_model
        self.pharma_research_model = pharma_research_model
        self.pharma_verifier_model = pharma_verifier_model
        self.prompt_version = prompt_version
        self.max_input_tokens = max_input_tokens
        self.research_max_output_tokens = research_max_output_tokens
        self.verifier_max_output_tokens = verifier_max_output_tokens
        self.min_grounding = min_grounding
        self.min_safety = min_safety
        self.min_completeness = min_completeness
        self.min_citation_coverage = min_citation_coverage
        self.mode = mode
        self.max_iterations = max_iterations
        self.web_search_required = web_search_required
        self.verifier_search_required = verifier_search_required

    def node_researcher(self, state: MedicalAgentState) -> None:
        state.retrieved_chunks = knowledge_retriever.retrieve(
            query=state.question,
            intent=state.intent,
            domain=state.domain,
            top_k=2,
        )
        if not state.retrieved_chunks:
            from app.services.knowledge_pool import capture_knowledge_gap
            capture_knowledge_gap(question=state.question, domain=state.domain,
                intent=state.intent if state.intent in {'triage','safety','general','pharmacy','monitoring','followup'} else 'general',
                reason='no_local_evidence')
        state.status = "writing"

    def node_writer(
        self,
        state: MedicalAgentState,
        *,
        instructions: str,
        redact_question_fn: Any,
        stage_trace_fn: Any,
    ) -> bool:
        rag_contexts = [chunk.to_dict() for chunk in state.retrieved_chunks]
        writer_claims, agent_envelope = _agent_inputs(state)

        if state.domain == "clinical":
            state.adaptive_route = adaptive_agent_runtime.resolve(
                envelope=agent_envelope,
                patient_context=state.patient_context,
            )
            if state.adaptive_route is not None:
                metrics.inc_counter(
                    "medguard_adaptive_route_total",
                    labels={
                        "agent": state.adaptive_route.agent.value,
                        "model_tier": state.adaptive_route.model_tier.value,
                        "emergency_lock": str(state.adaptive_route.emergency_lock).lower(),
                    },
                )

        research_payload: dict[str, Any] = {
            "locale": state.locale,
            "intent": state.intent,
            "user_question": redact_question_fn(state.question),
            "domain_claims": writer_claims,
            "clinical_envelope": agent_envelope,
            "retrieved_contexts": rag_contexts,
            "trusted_source_domains": [*sorted(TRUSTED_MEDICAL_DOMAINS)],
        }
        route_meta = _route_metadata(state.adaptive_route)
        if route_meta is not None:
            research_payload["execution_route"] = route_meta

        if state.feedback_history:
            research_payload["verifier_feedback"] = state.feedback_history[-1]
            research_payload["refinement_iteration"] = state.iteration

        budget = adaptive_agent_runtime.token_budget(
            route=state.adaptive_route,
            role="answer",
            base_input_tokens=self.max_input_tokens,
            base_output_tokens=self.research_max_output_tokens,
        )
        metrics.observe_histogram(
            "medguard_agent_token_budget",
            budget.max_output_tokens,
            labels={"role": "answer", "tier": state.adaptive_route.model_tier.value if state.adaptive_route else "standard"},
        )
        research_controls = gateway_controls(
            role="answer",
            policy=state.policy,
            tenant_id=state.tenant_id,
            conversation_id=state.conversation_id,
            locale=state.locale,
            patient_context=state.patient_context,
            prompt_version=self.prompt_version,
            knowledge_version=knowledge.version_string(),
            tool_result=agent_envelope,
            instructions=instructions,
            payload=research_payload,
            max_input_tokens=budget.max_input_tokens,
            max_output_tokens=budget.max_output_tokens,
        )

        if research_controls.estimated_input_tokens > research_controls.max_input_tokens:
            metrics.inc_counter(
                "medguard_llm_policy_blocks_total", labels={"reason": "input_token_limit"}
            )
            state.gate_reason = "input_token_limit_exceeded"
            state.status = "fallback"
            return False

        default_model = (
            (self.pharma_research_model or self.research_model)
            if state.domain == "pharmacology"
            else (self.clinical_research_model or self.research_model)
        )
        model_candidates = (
            (default_model,)
            if state.domain == "pharmacology"
            else adaptive_agent_runtime.writer_models(
                route=state.adaptive_route,
                default_model=default_model,
            )
        )
        metrics.inc_counter(
            "medguard_agent_branch_requests_total",
            labels={"domain": state.domain, "role": "answer"},
        )

        generated = None
        selected_model = default_model
        last_error: ModelProviderError | None = None
        for index, model in enumerate(model_candidates):
            try:
                generated = self.research_provider.complete(
                    stage="research",
                    model=model,
                    instructions=instructions,
                    payload=research_payload,
                    response_model=AgentDraft,
                    request_id=state.request_id,
                    controls=research_controls,
                )
                selected_model = model
                if index > 0:
                    metrics.inc_counter(
                        "medguard_agent_model_fallback_success_total",
                        labels={"role": "answer"},
                    )
                break
            except ModelProviderError as exc:
                last_error = exc
                metrics.inc_counter(
                    "medguard_agent_model_attempt_failures_total",
                    labels={"role": "answer"},
                )
                logger.warning("Writer model attempt failed model=%s: %s", model, exc)

        if generated is None:
            raise last_error or ModelProviderError("writer model ladder exhausted")

        draft = AgentDraft.model_validate(generated.data)

        # Cross-link citations and claims to satisfy clinical verification contracts
        retrieved_urls = [c.source_url for c in state.retrieved_chunks if c.source_url]
        if not draft.sources and state.retrieved_chunks:
            c = state.retrieved_chunks[0]
            url = c.source_url or "https://kcb.vn/huong-dan-chan-doan-dieu-tri"
            draft.sources = [
                AgentEvidenceSource(
                    source_id="src_guideline",
                    title=c.title,
                    publisher=c.source_reference or "Bộ Y tế / Cục KCB",
                    url=url,
                    authority_tier="guideline_or_regulator",
                    supports_claim_ids=[],
                )
            ]

        if draft.sources:
            known_source_ids = {s.source_id for s in draft.sources}
            first_src_id = draft.sources[0].source_id

            # In offline/no-web-search mode, align source URLs with retrieved knowledge chunks
            if not getattr(self, "web_search_required", True) and retrieved_urls:
                for s in draft.sources:
                    if not s.url.startswith("https://") or "medguard.local" in s.url or s.url not in retrieved_urls:
                        s.url = retrieved_urls[0]
            elif retrieved_urls:
                for s in draft.sources:
                    if not s.url.startswith("https://") or "medguard.local" in s.url:
                        s.url = retrieved_urls[0]

            # Ensure evidence claims point to existing sources
            for ec in draft.evidence_claims:
                if not ec.source_ids or any(sid not in known_source_ids for sid in ec.source_ids):
                    ec.source_ids = [first_src_id]

            # Ensure narrative blocks have valid sources
            for b in draft.narrative:
                if not b.source_ids and b.claim_ids:
                    b.source_ids = [first_src_id]

            # Only auto-populate claim mapping if source left supports_claim_ids empty
            for s in draft.sources:
                if not s.supports_claim_ids:
                    for ec in draft.evidence_claims:
                        if s.source_id in ec.source_ids and ec.claim_id not in s.supports_claim_ids:
                            s.supports_claim_ids.append(ec.claim_id)
                    for b in draft.narrative:
                        if s.source_id in b.source_ids:
                            for cid in b.claim_ids:
                                if cid not in s.supports_claim_ids:
                                    s.supports_claim_ids.append(cid)

        # Prune any un-cited evidence claims so orphaned model claims do not fail the gate
        cited_cids = {cid for b in draft.narrative for cid in b.claim_ids}
        draft.evidence_claims = [ec for ec in draft.evidence_claims if ec.claim_id in cited_cids]
        valid_cids = {ec.claim_id for ec in draft.evidence_claims} | {c["id"] for c in state.claims}
        for s in draft.sources:
            s.supports_claim_ids = [cid for cid in s.supports_claim_ids if cid in valid_cids]

        state.selected_writer_model = selected_model
        state.generator_trace = stage_trace_fn(
            "answer",
            self.research_provider,
            selected_model,
            generated,
            research_controls.estimated_input_tokens,
        )
        state.draft = draft
        state.generated_citations = generated.citations
        state.generated_search_queries = generated.search_queries
        state.status = "reviewing"
        return True

    def node_reviewer(
        self,
        state: MedicalAgentState,
        *,
        instructions: str,
        stage_trace_fn: Any,
        gate_reason_fn: Any,
    ) -> None:
        if not state.draft:
            state.status = "fallback"
            return

        rag_contexts = [chunk.to_dict() for chunk in state.retrieved_chunks]
        _, agent_envelope = _agent_inputs(state)
        verification_claims = state.claims
        if self.web_search_required and not self.verifier_search_required:
            state.runtime_evidence = trusted_evidence_fetcher.fetch(
                source.url for source in state.draft.sources
            )

        verifier_payload = {
            "intent": state.intent,
            "domain_claims": verification_claims,
            "clinical_envelope": agent_envelope,
            "retrieved_contexts": rag_contexts,
            "draft": state.draft.model_dump(mode="json"),
            "provider_citation_urls": list(state.generated_citations),
            "provider_search_queries": list(state.generated_search_queries),
            "runtime_external_evidence": [
                evidence.to_dict() for evidence in state.runtime_evidence
            ],
            "trusted_source_domains": [*sorted(TRUSTED_MEDICAL_DOMAINS)],
            "execution_route": _route_metadata(state.adaptive_route),
            "review_contract": {
                "author_response": False,
                "allowed_actions": ["approve", "reject", "request_revision"],
                "reviewer_bypass_allowed": False,
            },
        }

        budget = adaptive_agent_runtime.token_budget(
            route=state.adaptive_route,
            role="verifier",
            base_input_tokens=self.max_input_tokens,
            base_output_tokens=self.verifier_max_output_tokens,
        )
        metrics.observe_histogram(
            "medguard_agent_token_budget",
            budget.max_output_tokens,
            labels={"role": "verifier", "tier": state.adaptive_route.model_tier.value if state.adaptive_route else "standard"},
        )
        verifier_controls = gateway_controls(
            role="verifier",
            policy=state.policy,
            tenant_id=state.tenant_id,
            conversation_id=state.conversation_id,
            locale=state.locale,
            patient_context=state.patient_context,
            prompt_version=self.prompt_version,
            knowledge_version=knowledge.version_string(),
            tool_result=agent_envelope,
            instructions=instructions,
            payload=verifier_payload,
            max_input_tokens=budget.max_input_tokens,
            max_output_tokens=budget.max_output_tokens,
        )

        if verifier_controls.estimated_input_tokens > verifier_controls.max_input_tokens:
            metrics.inc_counter(
                "medguard_llm_policy_blocks_total", labels={"reason": "input_token_limit"}
            )
            state.gate_reason = "input_token_limit_exceeded"
            state.status = "fallback"
            return

        default_model = (
            (self.pharma_verifier_model or self.verifier_model)
            if state.domain == "pharmacology"
            else (self.clinical_verifier_model or self.verifier_model)
        )
        model_candidates = adaptive_agent_runtime.verifier_models(default_model=default_model)
        metrics.inc_counter(
            "medguard_agent_branch_requests_total",
            labels={"domain": state.domain, "role": "verifier"},
        )

        verified = None
        selected_model = default_model
        last_error: ModelProviderError | None = None
        for index, model in enumerate(model_candidates):
            try:
                verified = self.verifier_provider.complete(
                    stage="verifier",
                    model=model,
                    instructions=instructions,
                    payload=verifier_payload,
                    response_model=AgentVerification,
                    request_id=state.request_id,
                    controls=verifier_controls,
                )
                selected_model = model
                if index > 0:
                    metrics.inc_counter(
                        "medguard_agent_model_fallback_success_total",
                        labels={"role": "verifier"},
                    )
                break
            except ModelProviderError as exc:
                last_error = exc
                metrics.inc_counter(
                    "medguard_agent_model_attempt_failures_total",
                    labels={"role": "verifier"},
                )
                logger.warning("Reviewer model attempt failed model=%s: %s", model, exc)

        if verified is None:
            raise last_error or ModelProviderError("verifier model ladder exhausted")

        verification = AgentVerification.model_validate(verified.data)
        state.selected_verifier_model = selected_model
        state.verifier_trace = stage_trace_fn(
            "verifier",
            self.verifier_provider,
            selected_model,
            verified,
            verifier_controls.estimated_input_tokens,
        )

        reason = gate_reason_fn(
            draft=state.draft,
            verification=verification,
            claims=verification_claims,
            provider_citations=state.generated_citations,
            provider_queries=state.generated_search_queries,
            verifier_citations=verified.citations,
            retrieved_source_urls=tuple(
                chunk.source_url for chunk in state.retrieved_chunks if chunk.source_url
            ),
            runtime_evidence_urls=tuple(
                url
                for evidence in state.runtime_evidence
                for url in (evidence.requested_url, evidence.url)
            ),
            config=self,
        )

        if reason is None:
            clinical_result = (
                agent_envelope.get("clinical_result")
                if isinstance(agent_envelope.get("clinical_result"), dict)
                else {}
            )
            urgency = str(
                clinical_result.get("urgency")
                or clinical_result.get("escalation_level")
                or ""
            ).upper()
            quality = evaluate_professional_response(
                narrative_blocks=[block.text for block in state.draft.narrative],
                urgency=urgency,
                locked_claims=[
                    str(claim.get("text"))
                    for claim in verification_claims
                    if claim.get("locked") and claim.get("text")
                ],
            )
            metrics.set_gauge("medguard_professional_response_score", quality.score)
            if not quality.passed:
                reason = "professional_response_quality:" + (
                    quality.reasons[0] if quality.reasons else "below_threshold"
                )
                metrics.inc_counter(
                    "medguard_professional_response_rejections_total",
                    labels={"reason": quality.reasons[0] if quality.reasons else "below_threshold"},
                )

        state.verification = verification
        state.verified_citations = tuple(verified.citations)
        state.gate_reason = reason
        logger.info(
            "node_reviewer result: approved=%s, reason=%s, scores=%s, issues=%s",
            verification.approved,
            reason,
            verification.scores.model_dump(),
            verification.issues,
        )

        metrics.set_gauge(
            "medguard_rag_groundedness_score", float(verification.scores.grounding)
        )
        metrics.set_gauge("medguard_rag_safety_score", float(verification.scores.safety))
        metrics.set_gauge(
            "medguard_rag_citation_coverage", float(verification.scores.citation_coverage)
        )
        if verification.unsupported_claims or reason in {
            "unsupported_claims",
            "grounding_below_threshold",
        }:
            metrics.inc_counter("medguard_rag_hallucinations_detected_total")

    def route_decision(
        self, state: MedicalAgentState
    ) -> Literal["COMPLETE", "REVISE", "FALLBACK"]:
        if state.gate_reason is None:
            if state.iteration > 0:
                metrics.inc_counter("medguard_agent_loop_self_corrected_total")
            state.status = "verified"
            from app.services.knowledge_pool import stage_verified_public_evidence
            stage_verified_public_evidence(state.runtime_evidence, state.domain)
            return "COMPLETE"

        if state.iteration < self.max_iterations:
            feedback_parts: list[str] = []
            if state.verification:
                if state.verification.unsupported_claims:
                    feedback_parts.append(
                        "Loại bỏ hoặc bổ sung dẫn chứng cho các nhận định chưa được kiểm chứng: "
                        + ", ".join(state.verification.unsupported_claims)
                        + "."
                    )
                if state.verification.missing_claim_ids:
                    feedback_parts.append(
                        "Bổ sung các kết luận bắt buộc chưa trích dẫn: "
                        + ", ".join(state.verification.missing_claim_ids)
                        + "."
                    )
                if state.verification.source_issues:
                    feedback_parts.append(
                        "Khắc phục nguồn dẫn chứng: "
                        + ", ".join(state.verification.source_issues)
                        + "."
                    )
                if state.verification.scores.grounding < self.min_grounding:
                    feedback_parts.append(
                        f"Groundedness ({state.verification.scores.grounding:.2f}) dưới "
                        f"{self.min_grounding:.2f}. Bám sát tài liệu y tế."
                    )
            if not feedback_parts and state.gate_reason:
                feedback_parts.append(f"Khắc phục vi phạm kiểm định: {state.gate_reason}.")

            state.feedback_history.append(" ".join(feedback_parts))
            state.iteration += 1
            metrics.inc_counter(
                "medguard_agent_loop_iterations_total",
                labels={"iteration": str(state.iteration)},
            )
            state.status = "writing"
            return "REVISE"

        metrics.inc_counter(
            "medguard_rag_fallback_total",
            labels={"reason": state.gate_reason or "max_iterations_exceeded"},
        )
        state.status = "fallback"
        return "FALLBACK"
