"""StateGraph orchestrator for MedGuard AI (Harness -> Graph -> bounded Loop).

V14 keeps the dual-agent contract explicit:
- Writer owns patient-facing composition from structured state/evidence.
- Reviewer is a non-authoring quality gate. It may approve/reject and return
  revision issues, but never writes the patient response itself.
- Legacy deterministic prose is never supplied to Writer/Reviewer as evidence.
  Deterministic modules remain authoritative only for structured facts, safety
  constraints and fail-safe fallback behavior.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

from app.core.observability import metrics
from app.knowledge.loader import knowledge
from app.models.agents import (
    AgentDraft,
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
from app.services.agent_provider import StructuredModelProvider
from app.services.knowledge_retriever import RetrievedChunk, knowledge_retriever
from app.services.llm_control_plane import AgentRequestPolicy, gateway_controls
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
    """Convert a legacy GroundedAnswer dump into structured, non-prose input.

    V11/V12 ``enhance`` calls historically sent title/summary/template prose to
    the Writer, anchoring model output to the old response. V14 strips those
    presentation fields while retaining bounded clinical/workflow facts and
    safety/action constraints. The original answer remains only as fallback.
    """
    source = state.tool_result
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
            if key in {"age", "sex", "current_medications", "allergies", "conditions"}
            and value not in (None, "", [])
        },
        "communication_contract": {
            "compose_original_response": True,
            "legacy_template_prose_is_not_evidence": True,
            "answer_main_concern_first": True,
            "give_concrete_next_action": True,
            "separate_assessment_from_diagnosis": True,
            "avoid_generic_non_answers": True,
            "reviewer_is_non_authoring": True,
        },
    }
    # Preserve any additional non-presentation structured fields introduced by
    # a workflow without forwarding prose-first fields.
    for key, value in source.items():
        if key in _LEGACY_PRESENTATION_KEYS or key in envelope:
            continue
        if key in {"sources", "display_questions"}:
            continue
        envelope[key] = value
    return envelope


def _agent_inputs(state: MedicalAgentState) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return the only claims/envelope visible to Writer and Reviewer."""
    if _is_agent_first_envelope(state.tool_result):
        return state.claims, state.tool_result

    # title/summary are presentation artifacts in the legacy path. Excluding
    # them prevents the model from paraphrasing the deterministic answer while
    # retaining safety/finding/action/question constraints.
    visible_claims = [
        claim
        for claim in state.claims
        if claim.get("category") not in {"title", "summary"}
    ]
    return visible_claims, _structured_legacy_envelope(state)


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
        """Retrieve a compact curated context before the Writer runs."""
        state.retrieved_chunks = knowledge_retriever.retrieve(
            query=state.question,
            intent=state.intent,
            domain=state.domain,
            top_k=2,
        )
        state.status = "writing"

    def node_writer(
        self,
        state: MedicalAgentState,
        *,
        instructions: str,
        redact_question_fn: Any,
        stage_trace_fn: Any,
    ) -> bool:
        """Generate an original draft from structured state and evidence."""
        rag_contexts = [chunk.to_dict() for chunk in state.retrieved_chunks]
        agent_claims, agent_envelope = _agent_inputs(state)
        research_payload: dict[str, Any] = {
            "locale": state.locale,
            "intent": state.intent,
            "user_question": redact_question_fn(state.question),
            "domain_claims": agent_claims,
            "clinical_envelope": agent_envelope,
            "retrieved_contexts": rag_contexts,
            "trusted_source_domains": [*sorted(TRUSTED_MEDICAL_DOMAINS)],
        }

        if state.feedback_history:
            research_payload["verifier_feedback"] = state.feedback_history[-1]
            research_payload["refinement_iteration"] = state.iteration

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
            max_input_tokens=self.max_input_tokens,
            max_output_tokens=self.research_max_output_tokens,
        )

        if research_controls.estimated_input_tokens > research_controls.max_input_tokens:
            metrics.inc_counter(
                "medguard_llm_policy_blocks_total", labels={"reason": "input_token_limit"}
            )
            state.gate_reason = "input_token_limit_exceeded"
            state.status = "fallback"
            return False

        model = (
            (self.pharma_research_model or self.research_model)
            if state.domain == "pharmacology"
            else (self.clinical_research_model or self.research_model)
        )
        metrics.inc_counter(
            "medguard_agent_branch_requests_total",
            labels={"domain": state.domain, "role": "answer"},
        )

        generated = self.research_provider.complete(
            stage="research",
            model=model,
            instructions=instructions,
            payload=research_payload,
            response_model=AgentDraft,
            request_id=state.request_id,
            controls=research_controls,
        )
        draft = AgentDraft.model_validate(generated.data)
        state.generator_trace = stage_trace_fn(
            "answer",
            self.research_provider,
            model,
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
        """Judge the draft independently; never author patient-facing prose."""
        if not state.draft:
            state.status = "fallback"
            return

        rag_contexts = [chunk.to_dict() for chunk in state.retrieved_chunks]
        agent_claims, agent_envelope = _agent_inputs(state)
        if self.web_search_required and not self.verifier_search_required:
            state.runtime_evidence = trusted_evidence_fetcher.fetch(
                source.url for source in state.draft.sources
            )

        verifier_payload = {
            "intent": state.intent,
            "domain_claims": agent_claims,
            "clinical_envelope": agent_envelope,
            "retrieved_contexts": rag_contexts,
            "draft": state.draft.model_dump(mode="json"),
            "provider_citation_urls": list(state.generated_citations),
            "provider_search_queries": list(state.generated_search_queries),
            "runtime_external_evidence": [
                evidence.to_dict() for evidence in state.runtime_evidence
            ],
            "trusted_source_domains": [*sorted(TRUSTED_MEDICAL_DOMAINS)],
            "review_contract": {
                "author_response": False,
                "allowed_actions": ["approve", "reject", "request_revision"],
            },
        }

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
            max_input_tokens=self.max_input_tokens,
            max_output_tokens=self.verifier_max_output_tokens,
        )

        if verifier_controls.estimated_input_tokens > verifier_controls.max_input_tokens:
            metrics.inc_counter(
                "medguard_llm_policy_blocks_total", labels={"reason": "input_token_limit"}
            )
            state.gate_reason = "input_token_limit_exceeded"
            state.status = "fallback"
            return

        model = (
            (self.pharma_verifier_model or self.verifier_model)
            if state.domain == "pharmacology"
            else (self.clinical_verifier_model or self.verifier_model)
        )
        metrics.inc_counter(
            "medguard_agent_branch_requests_total",
            labels={"domain": state.domain, "role": "verifier"},
        )

        verified = self.verifier_provider.complete(
            stage="verifier",
            model=model,
            instructions=instructions,
            payload=verifier_payload,
            response_model=AgentVerification,
            request_id=state.request_id,
            controls=verifier_controls,
        )
        verification = AgentVerification.model_validate(verified.data)
        state.verifier_trace = stage_trace_fn(
            "verifier",
            self.verifier_provider,
            model,
            verified,
            verifier_controls.estimated_input_tokens,
        )

        reason = gate_reason_fn(
            draft=state.draft,
            verification=verification,
            claims=agent_claims,
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
        """Approve, request one Writer revision, or fail safely."""
        if state.gate_reason is None:
            if state.iteration > 0:
                metrics.inc_counter("medguard_agent_loop_self_corrected_total")
            state.status = "verified"
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
