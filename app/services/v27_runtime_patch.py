"""V27 runtime integration for contract-aware deterministic fallback.

The primary agent pipeline remains unchanged: Writer is still the sole author of
verified patient-facing prose and Reviewer remains non-authoring. This adapter
replaces the input fallback answer with a deterministic composition built from
the same ClinicalAgentContract before the existing pipeline executes.

V27.3 additionally applies presentation-only hygiene to the final returned
GroundedAnswer. It may remove transcript echoes, semantic duplicates and
punctuation artifacts, but it cannot change urgency, domain actions or clinical
claims.
"""

from __future__ import annotations

from functools import wraps
from typing import Any

from app.models.chat import ChatIntent, GroundedAnswer
from app.services.clinical_agent_contract import build_clinical_agent_contract
from app.services.clinical_contract_fallback import compose_contract_fallback


def _final_presentation_hygiene(answer: GroundedAnswer) -> GroundedAnswer:
    """Remove structured transcript echoes after all Writer/fallback enrichment.

    A patient-facing key point should be one bounded clinical point, never a
    multi-line replay of two or more user turns. Removing those echoes does not
    remove domain actions, safety notes, urgency or the canonical narrative.
    """
    from app.services.v27_2_answering_patch import _sanitize_answer

    cleaned = _sanitize_answer(answer)
    key_points = [
        str(value).strip()
        for value in list(cleaned.key_points or [])
        if str(value).strip() and "\n" not in str(value) and "\r" not in str(value)
    ]
    return cleaned.model_copy(update={"key_points": list(dict.fromkeys(key_points))[:5]})


def install_v27_runtime_fallback() -> None:
    """Patch ``AnswerAgentPipeline.generate_response`` exactly once."""

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

        final_answer = original(
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

        # Contract fallback and Writer can both enrich structured fields after
        # answering.py has already run. Reapply presentation-only hygiene at the
        # final boundary. Safety actions/urgency are intentionally untouched.
        return _final_presentation_hygiene(final_answer)

    AnswerAgentPipeline.generate_response = generate_response_with_contract_fallback
    AnswerAgentPipeline._v27_contract_fallback_installed = True
