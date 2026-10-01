"""V27.3 runtime integration for contract-aware fallback and output hygiene.

The primary agent pipeline remains unchanged: Writer is still the sole author of
verified patient-facing prose and Reviewer remains non-authoring. This adapter
builds the deterministic contextual fallback from the same ClinicalAgentContract,
then applies a presentation-only hygiene pass at the final runtime boundary.

The hygiene pass may remove duplicated/transcript-shaped presentation artifacts,
internal machine labels, or repeated punctuation. It must never change the
Safety Kernel urgency floor, remove an emergency/hard-stop action, or introduce
new clinical content.
"""

from __future__ import annotations

from functools import wraps
from typing import Any

from app.models.chat import ChatIntent, GroundedAnswer
from app.services.clinical_agent_contract import build_clinical_agent_contract
from app.services.clinical_contract_fallback import compose_contract_fallback
from app.services.v27_2_answering_patch import _sanitize_answer


def install_v27_runtime_fallback() -> None:
    """Patch ``AnswerAgentPipeline.generate_response`` exactly once.

    The adapter intentionally keeps the mature execution graph intact. It only
    injects the contract-aware fallback and enforces the same patient-output
    hygiene on both fallback and final verified/fallback results.
    """

    from app.services.answer_agents import AnswerAgentPipeline

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
        contextual_fallback = _sanitize_answer(
            compose_contract_fallback(fallback_answer, contract)
        )

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

        # Final presentation boundary: preserve all clinical authority decisions
        # while removing structural artifacts that can be introduced by either a
        # deterministic fallback or a verified Writer response.
        return _sanitize_answer(resolved)

    AnswerAgentPipeline.generate_response = generate_response_with_contract_fallback
    AnswerAgentPipeline._v27_contract_fallback_installed = True
