"""V27.1 runtime integration for contract-aware deterministic fallback.

The primary agent pipeline remains unchanged: Writer is still the sole author of
verified patient-facing prose and Reviewer remains non-authoring. This adapter
only replaces the *input fallback answer* with a deterministic composition built
from the same ClinicalAgentContract before the existing pipeline executes.

That means provider/configuration/circuit/timeout/rejection failures degrade to a
context-aware answer instead of the legacy ROUTINE/URGENT/EMERGENCY template.
"""

from __future__ import annotations

from functools import wraps
from typing import Any

from app.models.chat import ChatIntent, GroundedAnswer
from app.services.clinical_agent_contract import build_clinical_agent_contract
from app.services.clinical_contract_fallback import compose_contract_fallback


def install_v27_runtime_fallback() -> None:
    """Patch ``AnswerAgentPipeline.generate_response`` exactly once.

    Kept as a small adapter so V27.1 can be validated without duplicating or
    forking the mature agent execution graph. A later cleanup can move these
    three deterministic lines directly into ``generate_response`` once V27.1 is
    merged into the main clinical pipeline.
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
        contextual_fallback = compose_contract_fallback(fallback_answer, contract)

        return original(
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

    AnswerAgentPipeline.generate_response = generate_response_with_contract_fallback
    AnswerAgentPipeline._v27_contract_fallback_installed = True
