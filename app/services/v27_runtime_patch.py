"""V27.5 runtime integration for contract-aware fallback and output quality.

The primary agent pipeline remains unchanged: Writer is still the sole author of
verified patient-facing prose and Reviewer remains non-authoring. This adapter
builds the deterministic contextual fallback from the same ClinicalAgentContract,
then applies bounded current-concern refinement and presentation-only quality
passes at the final runtime boundary.

These passes must never change the Safety Kernel urgency floor, remove an
emergency/hard-stop action, or introduce new clinical content.
"""

from __future__ import annotations

from functools import wraps
from typing import Any

from app.models.chat import ChatIntent, ChatResponse, GroundedAnswer
from app.services.clinical_agent_contract import build_clinical_agent_contract
from app.services.clinical_contract_fallback import compose_contract_fallback
from app.services.fallback_response_refinement import refine_contract_fallback
from app.services.patient_response_surface import canonical_patient_response_text
from app.services.professional_response_quality import apply_professional_response_quality
from app.services.v27_2_answering_patch import _sanitize_answer
from app.services.optional_advice import attach_optional_advice


def _resolved_urgency(clinical_payload: dict[str, Any]) -> str:
    if bool(clinical_payload.get("emergency_flag")):
        return "EMERGENCY"
    return str(
        clinical_payload.get("urgency")
        or clinical_payload.get("escalation_level")
        or "ROUTINE"
    ).upper()


def _install_canonical_reply_surface() -> None:
    """Make ``reply`` match the verified narrative without changing the API schema.

    The frontend already treats verified Writer narrative as the canonical
    patient-visible surface. Keeping ``reply`` as the old summary caused the
    next client turn to send back a different assistant message than the patient
    had actually seen. This adapter preserves the string field for backwards
    compatibility while synchronizing its value only for verified responses.
    """
    if getattr(ChatResponse, "_v27_canonical_reply_installed", False):
        return

    original_init = ChatResponse.__init__

    @wraps(original_init)
    def init_with_canonical_reply(self: ChatResponse, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.reply = canonical_patient_response_text(
            answer=self.answer,
            verification_status=self.verification_status,
            fallback_text=self.reply,
        )

    ChatResponse.__init__ = init_with_canonical_reply  # type: ignore[method-assign]
    ChatResponse._v27_canonical_reply_installed = True


def install_v27_runtime_fallback() -> None:
    """Install narrow V27 runtime adapters exactly once.

    The adapter intentionally keeps the mature execution graph intact. It only
    injects the contract-aware fallback, aligns the compatibility reply with the
    already-verified patient surface, and enforces patient-visible quality at the
    final boundary. Safety authority remains upstream and immutable here.
    """

    from app.services.answer_agents import AnswerAgentPipeline

    _install_canonical_reply_surface()

    if getattr(AnswerAgentPipeline, "_v27_contract_fallback_installed", False):
        return

    original = AnswerAgentPipeline.generate_response

    @wraps(original)
    def generate_response_with_contract_fallback(
        self: Any,
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
        context = patient_context or {}
        contract = build_clinical_agent_contract(
            intent=intent,
            question=question,
            clinical_result=clinical_payload,
            patient_context=context,
        )
        contextual_fallback = compose_contract_fallback(fallback_answer, contract)
        contextual_fallback = refine_contract_fallback(contextual_fallback, contract)
        contextual_fallback = _sanitize_answer(contextual_fallback)

        resolved = original(
            self,
            fallback_answer=contextual_fallback,
            clinical_payload=clinical_payload,
            intent=intent,
            question=question,
            request_id=request_id,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            locale=locale,
            patient_context=context,
        )

        # Final presentation boundary: hygiene first, then a conservative
        # de-duplication pass. V27.5 leaves EMERGENCY output untouched and never
        # mutates structured claims/actions/safety notes/questions.
        sanitized = attach_optional_advice(_sanitize_answer(resolved), clinical_payload, _resolved_urgency(clinical_payload))
        return apply_professional_response_quality(
            sanitized,
            urgency=_resolved_urgency(clinical_payload),
            intent=str(intent),
        )

    AnswerAgentPipeline.generate_response = generate_response_with_contract_fallback
    AnswerAgentPipeline._v27_contract_fallback_installed = True
