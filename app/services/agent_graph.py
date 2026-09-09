"""StateGraph Orchestrator for MedGuard AI System (Harness ⊃ Graph ⊃ Loop).

Preserves 100% LiteLLM Gateway integration while implementing:
- Tầng 1 (Harness): Security, controls, KnowledgeRetriever, and LiteLLM Gateway providers.
- Tầng 2 (Loop): Inner deterministic schema/claim loop + Outer verifier refinement feedback loop (max 2 iterations).
- Tầng 3 (Graph): StateGraph coordinating Researcher (parallel fan-out) -> Writer (act+verify loop) -> Reviewer (fresh context) -> Conditional Routing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

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
from app.services.llm_control_plane import (
    AgentRequestPolicy,
    gateway_controls,
)


@dataclass
class MedicalAgentState:
    """Shared state object flowing across graph nodes."""

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

    # Accumulated state
    retrieved_chunks: list[RetrievedChunk] = field(default_factory=list)
    draft: AgentDraft | None = None
    generator_trace: AgentStageTrace | None = None
    generated_citations: tuple[str, ...] = ()
    generated_search_queries: tuple[str, ...] = ()

    verifier_trace: AgentStageTrace | None = None
    verification: AgentVerification | None = None
    verified_citations: tuple[str, ...] = ()
    gate_reason: str | None = None

    iteration: int = 0
    max_iterations: int = 2
    feedback_history: list[str] = field(default_factory=list)
    status: Literal["researching", "writing", "reviewing", "verified", "fallback", "shadow"] = "researching"


class MedicalAgentGraph:
    """StateGraph orchestrating multi-role clinical reasoning with verification loops."""

    def __init__(
        self,
        *,
        research_provider: StructuredModelProvider,
        verifier_provider: StructuredModelProvider,
        research_model: str,
        verifier_model: str,
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
    ) -> None:
        self.research_provider = research_provider
        self.verifier_provider = verifier_provider
        self.research_model = research_model
        self.verifier_model = verifier_model
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

    def node_researcher(self, state: MedicalAgentState) -> None:
        """Node 1: Parallel/Fan-out knowledge retrieval from curated clinical files."""
        retrieved = knowledge_retriever.retrieve(
            query=state.question,
            intent=state.intent,
            top_k=5,
        )
        state.retrieved_chunks = retrieved
        state.status = "writing"

    def node_writer(
        self,
        state: MedicalAgentState,
        *,
        instructions: str,
        redact_question_fn: Any,
        stage_trace_fn: Any,
    ) -> bool:
        """Node 2 (with internal Loop 1): Generate answer draft and verify deterministic constraints."""
        rag_contexts = [c.to_dict() for c in state.retrieved_chunks]
        research_payload: dict[str, Any] = {
            "locale": state.locale,
            "intent": state.intent,
            "user_question": redact_question_fn(state.question),
            "domain_claims": state.claims,
            "retrieved_contexts": rag_contexts,
            "trusted_source_domains": [
                "who.int", "nice.org.uk", "nhs.uk", "fda.gov",
                "ema.europa.eu", "cdc.gov", "nih.gov", "ncbi.nlm.nih.gov",
            ],
        }

        # Inject feedback from Reviewer if this is a refinement loop
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
            tool_result=state.tool_result,
            instructions=instructions,
            payload=research_payload,
            max_input_tokens=self.max_input_tokens,
            max_output_tokens=self.research_max_output_tokens,
        )

        if research_controls.estimated_input_tokens > research_controls.max_input_tokens:
            metrics.inc_counter("medguard_llm_policy_blocks_total", labels={"reason": "input_token_limit"})
            state.gate_reason = "input_token_limit_exceeded"
            state.status = "fallback"
            return False

        generated = self.research_provider.complete(
            stage="research",
            model=self.research_model,
            instructions=instructions,
            payload=research_payload,
            response_model=AgentDraft,
            request_id=state.request_id,
            controls=research_controls,
        )

        draft = AgentDraft.model_validate(generated.data)
        generator_trace = stage_trace_fn(
            "answer",
            self.research_provider,
            self.research_model,
            generated,
            research_controls.estimated_input_tokens,
        )

        state.draft = draft
        state.generator_trace = generator_trace
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
        """Node 3: Independent quality, safety and groundedness verification with fresh context."""
        if not state.draft:
            state.status = "fallback"
            return

        rag_contexts = [c.to_dict() for c in state.retrieved_chunks]
        verifier_payload = {
            "intent": state.intent,
            "domain_claims": state.claims,
            "retrieved_contexts": rag_contexts,
            "draft": state.draft.model_dump(mode="json"),
            "provider_citation_urls": list(state.generated_citations),
            "provider_search_queries": list(state.generated_search_queries),
            "trusted_source_domains": [
                "who.int", "nice.org.uk", "nhs.uk", "fda.gov",
                "ema.europa.eu", "cdc.gov", "nih.gov", "ncbi.nlm.nih.gov",
            ],
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
            tool_result=state.tool_result,
            instructions=instructions,
            payload=verifier_payload,
            max_input_tokens=self.max_input_tokens,
            max_output_tokens=self.verifier_max_output_tokens,
        )

        if verifier_controls.estimated_input_tokens > verifier_controls.max_input_tokens:
            metrics.inc_counter("medguard_llm_policy_blocks_total", labels={"reason": "input_token_limit"})
            state.gate_reason = "input_token_limit_exceeded"
            state.status = "fallback"
            return

        verified = self.verifier_provider.complete(
            stage="verifier",
            model=self.verifier_model,
            instructions=instructions,
            payload=verifier_payload,
            response_model=AgentVerification,
            request_id=state.request_id,
            controls=verifier_controls,
        )

        verification = AgentVerification.model_validate(verified.data)
        verifier_trace = stage_trace_fn(
            "verifier",
            self.verifier_provider,
            self.verifier_model,
            verified,
            verifier_controls.estimated_input_tokens,
        )

        reason = gate_reason_fn(
            draft=state.draft,
            verification=verification,
            claims=state.claims,
            provider_citations=state.generated_citations,
            provider_queries=state.generated_search_queries,
            verifier_citations=verified.citations,
            config=self,
        )

        state.verification = verification
        state.verifier_trace = verifier_trace
        state.verified_citations = tuple(verified.citations)
        state.gate_reason = reason

        # Record Golden Signals
        metrics.set_gauge("medguard_rag_groundedness_score", float(verification.scores.grounding))
        metrics.set_gauge("medguard_rag_safety_score", float(verification.scores.safety))
        metrics.set_gauge("medguard_rag_citation_coverage", float(verification.scores.citation_coverage))
        if verification.unsupported_claims or reason in {"unsupported_claims", "grounding_below_threshold"}:
            metrics.inc_counter("medguard_rag_hallucinations_detected_total")

    def route_decision(self, state: MedicalAgentState) -> Literal["COMPLETE", "REVISE", "FALLBACK"]:
        """Conditional routing edge with verification feedback loop."""
        if state.gate_reason is None:
            if state.iteration > 0:
                metrics.inc_counter("medguard_agent_loop_self_corrected_total")
            state.status = "verified"
            return "COMPLETE"

        # If rejected but iterations remain, construct structured feedback
        if state.iteration < self.max_iterations:
            feedback_parts: list[str] = []
            if state.verification:
                if state.verification.unsupported_claims:
                    feedback_parts.append(f"Loại bỏ hoặc bổ sung dẫn chứng cho các nhận định chưa được kiểm chứng: {', '.join(state.verification.unsupported_claims)}.")
                if state.verification.missing_claim_ids:
                    feedback_parts.append(f"Bổ sung các kết luận bắt buộc chưa trích dẫn: {', '.join(state.verification.missing_claim_ids)}.")
                if state.verification.source_issues:
                    feedback_parts.append(f"Khắc phục nguồn dẫn chứng: {', '.join(state.verification.source_issues)}.")
                if state.verification.scores.grounding < self.min_grounding:
                    feedback_parts.append(f"Groundedness ({state.verification.scores.grounding:.2f}) dưới {self.min_grounding:.2f}. Bám sát tài liệu y tế.")
            if not feedback_parts and state.gate_reason:
                feedback_parts.append(f"Khắc phục vi phạm kiểm định: {state.gate_reason}.")

            state.feedback_history.append(" ".join(feedback_parts))
            state.iteration += 1
            metrics.inc_counter("medguard_agent_loop_iterations_total", labels={"iteration": str(state.iteration)})
            state.status = "writing"
            return "REVISE"

        # Max iterations reached -> Fail-safe Fallback
        metrics.inc_counter("medguard_rag_fallback_total", labels={"reason": state.gate_reason or "max_iterations_exceeded"})
        state.status = "fallback"
        return "FALLBACK"
