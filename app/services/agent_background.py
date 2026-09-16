"""Non-blocking shadow execution for the optional LLM gateway.

Patient-facing chat must not wait for a small local model.  This runner accepts
every request admitted by the HTTP layer, evaluates the already grounded
deterministic answer.  A single local worker may build a backlog, but it must
not misreport that backlog as a gateway outage.  The default shadow path only
records provider-neutral outcome data.  An explicit progressive-enhancement
setting may atomically replace the durable answer only after the full writer,
evidence and release-gate contract succeeds.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from dataclasses import replace
from threading import Lock
from time import monotonic, sleep
from typing import Any, Literal

import httpx

from app.core.config import settings
from app.core.observability import metrics
from app.models.agents import ShadowVerifierAssessment, ShadowWriterAssessment
from app.models.chat import ChatIntent, GroundedAnswer
from app.services.agent_provider import LiteLLMResponsesProvider, ModelProviderError, ProviderResult
from app.services.answer_agents import AnswerAgentConfig, AnswerAgentPipeline, _redact_question
from app.services.audit import AuditEvent, audit_store
from app.services.chat_history import chat_history_store
from app.services.circuit import model_circuit
from app.services.knowledge_retriever import resolve_domain
from app.services.llm_control_plane import gateway_controls, policy_for_intent


_SHADOW_WRITER_INSTRUCTIONS = """You are MedGuard's Vietnamese medical communication quality assessor.
Evaluate the already generated deterministic answer; do not rewrite it, diagnose, prescribe, or add facts.
Check whether triage wording matches the action, the highest-priority action appears early, uncertainty is calibrated, and tone is professional.
Communication positivity is not sentiment alone: urgent language may be alarming but appropriate; false reassurance and panic-inducing language are unsafe.
Return only the requested compact structured object."""

_SHADOW_VERIFIER_INSTRUCTIONS = """You are an independent MedGuard safety reviewer.
Verify the writer assessment against the supplied deterministic answer and rubric. Do not add medical facts or treatment.
The safety_notes field contains conditional future warning signs; do not treat those warnings as symptoms the user currently reports.
Approve only when there is no false reassurance, triage/action contradiction, hidden urgent action, diagnosis certainty, or unsafe instruction.
Return safety_score, clarity_score, and consistency_score as decimals from 0.0 to 1.0.
Return only the requested compact structured object."""


@dataclass(frozen=True)
class ShadowQualityResult:
    status: Literal["shadow", "error"]
    approved: bool | None = None
    writer: ShadowWriterAssessment | None = None
    verifier: ShadowVerifierAssessment | None = None


def _record_stage(role: str, result: ProviderResult) -> None:
    metrics.inc_counter(
        "medguard_llm_stage_requests_total",
        labels={"role": role, "status": "success", "cache_hit": str(bool(result.cache_hit)).lower()},
    )
    metrics.observe_histogram("medguard_llm_stage_latency_ms", result.latency_ms, labels={"role": role})
    metrics.observe_histogram("medguard_llm_input_tokens", result.input_tokens, labels={"role": role, "source": "actual"})
    metrics.observe_histogram("medguard_llm_output_tokens", result.output_tokens, labels={"role": role})


class CompactShadowQualityPipeline:
    """Two-stage local-model assessment that never changes a released answer."""

    def __init__(self, writer: LiteLLMResponsesProvider, verifier: LiteLLMResponsesProvider) -> None:
        self.writer = writer
        self.verifier = verifier

    @staticmethod
    def _complete_with_retry(provider: LiteLLMResponsesProvider, **values: Any) -> ProviderResult:
        """Retry gateway/parse failures with bounded exponential backoff.

        This runs only in the background worker.  It therefore improves the
        chance of eventual gateway completion without extending the public
        chat response time.
        """
        attempts = settings.agent_background_max_attempts
        gateway_deadline = monotonic() + settings.agent_background_gateway_wait_seconds
        for attempt in range(1, attempts + 1):
            CompactShadowQualityPipeline._wait_until_gateway_ready(gateway_deadline)
            try:
                return provider.complete(**values)
            except ModelProviderError:
                if attempt >= attempts:
                    raise
                metrics.inc_counter(
                    "medguard_llm_background_retry_total",
                    labels={
                        "role": str(values.get("stage", "unknown")),
                        "attempt": str(attempt + 1),
                    },
                )
                sleep(settings.agent_background_retry_base_seconds * (2 ** (attempt - 1)))
        raise RuntimeError("unreachable background retry state")

    @staticmethod
    def _wait_until_gateway_ready(deadline: float) -> None:
        """Pause background work during a gateway restart instead of spending retries."""
        if not settings.llm_gateway_url or settings.agent_background_gateway_wait_seconds == 0:
            return
        gateway_root = settings.llm_gateway_url.removesuffix("/v1")
        while True:
            try:
                response = httpx.get(
                    f"{gateway_root}/health/liveliness",
                    headers={"Authorization": f"Bearer {settings.llm_gateway_api_key or ''}"},
                    timeout=settings.llm_gateway_health_timeout_seconds,
                )
                response.raise_for_status()
                return
            except httpx.HTTPError as exc:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise ModelProviderError(
                        "LLM gateway did not become ready before the background wait deadline"
                    ) from exc
                sleep(min(2.0, remaining))

    @staticmethod
    def _contract(answer: GroundedAnswer) -> dict[str, Any]:
        return {
            "title": answer.title,
            "summary": answer.summary,
            "next_steps": answer.next_steps[:3],
            "safety_notes": answer.safety_notes[:2],
            "questions": answer.questions[:2],
            "requires_human_review": answer.requires_human_review,
            "limitations": answer.limitations[:2],
        }

    def evaluate(
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
    ) -> ShadowQualityResult:
        domain = resolve_domain(intent, question)
        policy = policy_for_intent(intent)
        contract = self._contract(answer)
        writer_payload = {
            "locale": locale,
            "intent": intent,
            "user_question": _redact_question(question),
            "deterministic_answer": contract,
            "rubric": {
                "critical": [
                    "triage and action must agree",
                    "urgent action must not be delayed",
                    "no diagnosis certainty or unsafe self-treatment",
                ],
                "communication": [
                    "direct",
                    "calm and professional",
                    "calibrated uncertainty",
                ],
            },
        }
        writer_controls = gateway_controls(
            role="answer",
            policy=policy,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            locale=locale,
            patient_context=patient_context,
            prompt_version=settings.agent_prompt_version,
            knowledge_version="compact-shadow-v1",
            tool_result=contract,
            instructions=_SHADOW_WRITER_INSTRUCTIONS,
            payload=writer_payload,
            max_input_tokens=settings.agent_max_input_tokens,
            # Gemini 3.8 includes thinking tokens in its output allowance. A
            # 320-token cap could therefore truncate the structured object to
            # just an opening brace even at low reasoning effort.
            max_output_tokens=min(settings.agent_background_research_max_output_tokens, 800),
        )
        writer_model = (
            settings.pharma_research_model if domain == "pharmacology" else settings.clinical_research_model
        )
        writer_result = self._complete_with_retry(self.writer,
            stage="research",
            model=writer_model,
            instructions=_SHADOW_WRITER_INSTRUCTIONS,
            payload=writer_payload,
            response_model=ShadowWriterAssessment,
            request_id=request_id,
            controls=writer_controls,
        )
        _record_stage("answer", writer_result)
        writer_assessment = ShadowWriterAssessment.model_validate(writer_result.data)

        verifier_payload = {
            "intent": intent,
            "deterministic_answer": contract,
            "writer_assessment": writer_assessment.model_dump(mode="json"),
        }
        verifier_controls = gateway_controls(
            role="verifier",
            policy=policy,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            locale=locale,
            patient_context=patient_context,
            prompt_version=settings.agent_prompt_version,
            knowledge_version="compact-shadow-v1",
            tool_result=contract,
            instructions=_SHADOW_VERIFIER_INSTRUCTIONS,
            payload=verifier_payload,
            max_input_tokens=settings.agent_max_input_tokens,
            max_output_tokens=min(settings.agent_background_verifier_max_output_tokens, 500),
        )
        verifier_model = (
            settings.pharma_verifier_model if domain == "pharmacology" else settings.clinical_verifier_model
        )
        verifier_result = self._complete_with_retry(self.verifier,
            stage="verifier",
            model=verifier_model,
            instructions=_SHADOW_VERIFIER_INSTRUCTIONS,
            payload=verifier_payload,
            response_model=ShadowVerifierAssessment,
            request_id=request_id,
            controls=verifier_controls,
        )
        _record_stage("verifier", verifier_result)
        verifier_assessment = ShadowVerifierAssessment.model_validate(verifier_result.data)
        model_circuit.record_success()
        return ShadowQualityResult(
            status="shadow",
            approved=verifier_assessment.approved,
            writer=writer_assessment,
            verifier=verifier_assessment,
        )


_background_pipeline = CompactShadowQualityPipeline(
    writer=LiteLLMResponsesProvider(
        api_key=settings.llm_gateway_api_key,
        base_url=settings.llm_gateway_url,
        timeout_seconds=settings.agent_background_stage_timeout_seconds,
        reasoning_effort=settings.research_reasoning_effort,
        web_search_enabled=False,
        api_style=settings.llm_gateway_api_style,
    ),
    verifier=LiteLLMResponsesProvider(
        api_key=settings.llm_gateway_api_key,
        base_url=settings.llm_gateway_url,
        timeout_seconds=settings.agent_background_stage_timeout_seconds,
        reasoning_effort=settings.verifier_reasoning_effort,
        web_search_enabled=False,
        api_style=settings.llm_gateway_api_style,
    ),
)


_background_promotion_pipeline = AnswerAgentPipeline(
    config=replace(
        AnswerAgentConfig.from_settings(),
        mode="enforced",
        total_timeout_seconds=settings.agent_background_total_timeout_seconds,
        research_max_output_tokens=settings.agent_background_research_max_output_tokens,
        verifier_max_output_tokens=settings.agent_background_verifier_max_output_tokens,
    ),
    research_provider=LiteLLMResponsesProvider(
        api_key=settings.llm_gateway_api_key,
        base_url=settings.llm_gateway_url,
        timeout_seconds=settings.agent_background_stage_timeout_seconds,
        reasoning_effort=settings.research_reasoning_effort,
        web_search_enabled=settings.agent_web_search_enabled,
        api_style=settings.llm_gateway_api_style,
    ),
    verifier_provider=LiteLLMResponsesProvider(
        api_key=settings.llm_gateway_api_key,
        base_url=settings.llm_gateway_url,
        timeout_seconds=settings.agent_background_stage_timeout_seconds,
        reasoning_effort=settings.verifier_reasoning_effort,
        web_search_enabled=settings.verifier_web_search_enabled,
        api_style=settings.llm_gateway_api_style,
    ),
    circuit=model_circuit,
)


class BackgroundAgentRunner:
    """Lossless-in-process admission with bounded worker concurrency.

    ``max_pending`` is retained as a compatibility setting, but is now a soft
    backlog warning threshold rather than a rejection limit.  Admission is
    already bounded at the public API by tenant rate limiting.  Production
    deployments still need a durable queue if work must survive process
    restarts; the local executor deliberately optimizes the developer profile
    for low response latency and no ``dropped_busy`` answers.
    """

    def __init__(self, max_pending: int = 100, *, max_workers: int = 1) -> None:
        self._backlog_warning_threshold = max_pending
        self._state_lock = Lock()
        self._pending = 0
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="medguard-shadow-agent",
        )

    @property
    def pending_count(self) -> int:
        with self._state_lock:
            return self._pending

    def _change_pending(self, delta: int) -> int:
        with self._state_lock:
            self._pending = max(0, self._pending + delta)
            pending = self._pending
        metrics.set_gauge("medguard_llm_background_pending", float(pending))
        return pending

    def submit(
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
    ) -> bool:
        pending = self._change_pending(1)
        metrics.inc_counter(
            "medguard_llm_background_total",
            labels={"outcome": "submitted"},
        )
        if pending > self._backlog_warning_threshold:
            metrics.inc_counter(
                "medguard_llm_background_total",
                labels={"outcome": "backlog_above_warning_threshold"},
            )
        try:
            self._executor.submit(
                self._run,
                answer=answer,
                intent=intent,
                question=question,
                request_id=request_id,
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                locale=locale,
                patient_context=patient_context,
            )
        except RuntimeError:
            self._change_pending(-1)
            metrics.inc_counter(
                "medguard_llm_background_total",
                labels={"outcome": "executor_unavailable"},
            )
            return False
        return True

    def _run(self, **values: Any) -> None:
        request_id = str(values["request_id"])
        tenant_id = str(values["tenant_id"])
        try:
            if settings.agent_background_promote_verified:
                enhanced = _background_promotion_pipeline.enhance(**values)
                trace = enhanced.agent_trace
                status = trace.status if trace else "error"
                approved = status == "verified"
                metrics.inc_counter(
                    "medguard_llm_background_total",
                    labels={"outcome": status},
                )
                audit_store.append(
                    AuditEvent(
                        request_id=request_id,
                        tenant_id=tenant_id,
                        action="chat.agent_background_promotion",
                        payload_type="GroundedAnswer",
                        metadata={
                            "conversation_id": values["conversation_id"],
                            "intent": values["intent"],
                            "status": status,
                            "approved": approved,
                            "fallback_reason": trace.fallback_reason if trace else "missing_trace",
                        },
                    )
                )
                if approved:
                    public_answer = enhanced.model_copy(update={"agent_trace": None})
                    chat_history_store.update_answer_and_verification(
                        tenant_id,
                        str(values["conversation_id"]),
                        request_id,
                        answer=public_answer,
                        verification_status="verified",
                        answer_origin="gateway_verified",
                    )
                else:
                    chat_history_store.update_verification(
                        tenant_id,
                        str(values["conversation_id"]),
                        request_id,
                        verification_status=status,
                        answer_origin="deterministic_fallback",
                    )
                return

            evaluated = _background_pipeline.evaluate(**values)
            status = evaluated.status
            public_status = status
            answer_origin = "deterministic"
            metrics.inc_counter(
                "medguard_llm_background_total",
                labels={"outcome": status},
            )
            audit_store.append(
                AuditEvent(
                    request_id=request_id,
                    tenant_id=tenant_id,
                    action="chat.agent_shadow",
                    payload_type="GroundedAnswer",
                    metadata={
                        "conversation_id": values["conversation_id"],
                        "intent": values["intent"],
                        "status": status,
                        "approved": evaluated.approved,
                        "communication_class": (
                            evaluated.writer.communication_class if evaluated.writer else None
                        ),
                        "safety_score": (
                            evaluated.verifier.safety_score if evaluated.verifier else None
                        ),
                    },
                )
            )
            chat_history_store.update_verification(
                tenant_id,
                str(values["conversation_id"]),
                request_id,
                verification_status=public_status,
                answer_origin=answer_origin,
            )
        except Exception as exc:  # keep background failures away from the request path
            model_circuit.record_failure()
            metrics.inc_counter(
                "medguard_llm_background_total",
                labels={"outcome": "error"},
            )
            audit_store.append(
                AuditEvent(
                    request_id=request_id,
                    tenant_id=tenant_id,
                    action="chat.agent_shadow",
                    payload_type="GroundedAnswer",
                    metadata={
                        "conversation_id": values["conversation_id"],
                        "intent": values["intent"],
                        "status": "error",
                        "error_type": type(exc).__name__,
                    },
                )
            )
            chat_history_store.update_verification(
                tenant_id,
                str(values["conversation_id"]),
                request_id,
                verification_status="error",
                answer_origin="deterministic_fallback",
            )
        finally:
            self._change_pending(-1)

    def shutdown(self, *, wait: bool = True) -> None:
        """Release worker threads; primarily useful for isolated tests."""
        self._executor.shutdown(wait=wait)


background_agent_runner = BackgroundAgentRunner(
    settings.agent_background_max_pending,
    max_workers=settings.agent_background_workers,
)
