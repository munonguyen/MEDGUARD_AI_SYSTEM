from __future__ import annotations

import re
from typing import Any

from app.services.clinical_text import normalize_search_text
from app.services.response_policy.models import (
    ClinicalResponsePolicy,
    CommunicationGoal,
    ReassurancePolicy,
    ResponseDepth,
    TargetLength,
)


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _knowledge_only(question: str) -> bool:
    norm = normalize_search_text(question)
    self_report = bool(
        re.search(
            r"\b(?:toi|minh|em|con|me toi|bo toi|nguoi nha).*\b(?:dau|sot|kho tho|chong mat|te|yeu|sung|ngua|non|met|ho)\b",
            norm,
        )
    )
    if self_report:
        return False
    return bool(
        re.search(
            r"\b(?:la gi|nghia la gi|tai sao|co che|khac nhau|trieu chung cua|dau hieu cua|benh .* la gi)\b",
            norm,
        )
    )


def _simple_direct_question(question: str) -> bool:
    norm = normalize_search_text(question)
    return bool(
        re.search(
            r"\b(?:bao nhieu|may do|nguong|bao lau|co phai la sot|chi so nao)\b",
            norm,
        )
    ) and len(norm.split()) <= 18


def _reasoning_mechanisms(reasoning_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(reasoning_payload, dict):
        return []
    values = reasoning_payload.get("mechanisms") or []
    return [item for item in values if isinstance(item, dict)]


def _leading_mechanism(reasoning_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    mechanisms = _reasoning_mechanisms(reasoning_payload)
    for item in mechanisms:
        if _text(item.get("role")) == "leading":
            return item
    return mechanisms[0] if mechanisms else None


def _reassurance_from_reasoning(
    *,
    urgency: str,
    assessment_state: str,
    result: dict[str, Any],
    reasoning_payload: dict[str, Any] | None,
) -> ReassurancePolicy:
    if urgency != "ROUTINE" or assessment_state != "UNDERSTOOD":
        return ReassurancePolicy(allowed=False)

    red_flags = result.get("red_flags") or []
    if isinstance(red_flags, list) and any(_text(item) for item in red_flags):
        return ReassurancePolicy(allowed=False)

    leading = _leading_mechanism(reasoning_payload)
    if not leading:
        return ReassurancePolicy(allowed=False)

    support_level = _text(leading.get("support_level")).lower()
    if support_level not in {"supported", "plausible"}:
        return ReassurancePolicy(allowed=False)

    basis_values = leading.get("evidence_for") or []
    basis = tuple(_text(value) for value in basis_values if _text(value))[:3]
    limitations: list[str] = []
    statement = _text(leading.get("patient_safe_statement"))
    if statement:
        limitations.append(statement)
    for value in (reasoning_payload or {}).get("reasoning_limits", [])[:2]:
        text = _text(value)
        if text:
            limitations.append(text)

    return ReassurancePolicy(
        allowed=True,
        strength="moderate" if support_level == "supported" else "cautious",
        basis=basis,
        limitations=tuple(dict.fromkeys(limitations))[:3],
    )


def build_response_policy(
    *,
    intent: str,
    question: str,
    urgency: str,
    assessment_state: str,
    result: dict[str, Any],
    reasoning_payload: dict[str, Any] | None,
) -> ClinicalResponsePolicy:
    urgency = urgency.upper()

    if urgency == "EMERGENCY" or bool(result.get("emergency_flag")):
        return ClinicalResponsePolicy(
            communication_goal=CommunicationGoal.EMERGENCY_ACTION,
            response_depth=ResponseDepth.D5_EMERGENCY,
            explanation_required=True,
            mechanism_required=False,
            reassurance=ReassurancePolicy(allowed=False),
            action_first=True,
            question_budget=0,
            target_length=TargetLength(70, 140),
            required_sections=(
                "immediate_action",
                "why_this_is_concerning",
                "uncertainty_boundary",
            ),
        )

    if urgency == "URGENT":
        return ClinicalResponsePolicy(
            communication_goal=CommunicationGoal.URGENT_GUIDANCE,
            response_depth=ResponseDepth.D4_URGENT,
            explanation_required=True,
            mechanism_required=bool(_reasoning_mechanisms(reasoning_payload)),
            reassurance=ReassurancePolicy(allowed=False),
            action_first=False,
            question_budget=1,
            target_length=TargetLength(100, 180),
            required_sections=(
                "clinical_interpretation",
                "why_concerning",
                "next_action",
                "uncertainty_boundary",
            ),
        )

    if assessment_state in {"INSUFFICIENT_CONTEXT", "PARTIALLY_UNDERSTOOD"}:
        return ClinicalResponsePolicy(
            communication_goal=CommunicationGoal.CLARIFY_UNCERTAINTY,
            response_depth=ResponseDepth.D3_CLINICAL_GUIDANCE,
            explanation_required=True,
            mechanism_required=False,
            reassurance=ReassurancePolicy(allowed=False),
            action_first=False,
            question_budget=1,
            target_length=TargetLength(90, 160),
            required_sections=(
                "what_is_understood",
                "what_remains_unclear",
                "highest_information_question",
            ),
        )

    if intent == "safety":
        return ClinicalResponsePolicy(
            communication_goal=CommunicationGoal.MEDICATION_SAFETY,
            response_depth=ResponseDepth.D3_CLINICAL_GUIDANCE,
            explanation_required=True,
            mechanism_required=True,
            reassurance=ReassurancePolicy(allowed=False),
            action_first=False,
            question_budget=1,
            target_length=TargetLength(100, 200),
            required_sections=(
                "medication_risk_interpretation",
                "mechanism_or_interaction_explanation",
                "safe_next_action",
            ),
        )

    if _knowledge_only(question):
        direct = _simple_direct_question(question)
        return ClinicalResponsePolicy(
            communication_goal=CommunicationGoal.EDUCATE,
            response_depth=ResponseDepth.D1_DIRECT if direct else ResponseDepth.D2_EXPLAIN,
            explanation_required=not direct,
            mechanism_required=not direct,
            reassurance=ReassurancePolicy(allowed=False),
            action_first=False,
            question_budget=0,
            target_length=TargetLength(40, 90) if direct else TargetLength(80, 160),
            required_sections=("direct_answer",) if direct else ("definition", "plain_language_explanation"),
        )

    reassurance = _reassurance_from_reasoning(
        urgency=urgency,
        assessment_state=assessment_state,
        result=result,
        reasoning_payload=reasoning_payload,
    )
    return ClinicalResponsePolicy(
        communication_goal=(
            CommunicationGoal.REASSURE_AND_GUIDE
            if reassurance.allowed
            else CommunicationGoal.EXPLAIN_SYMPTOM
        ),
        response_depth=ResponseDepth.D3_CLINICAL_GUIDANCE,
        explanation_required=True,
        mechanism_required=bool(_reasoning_mechanisms(reasoning_payload)),
        reassurance=reassurance,
        action_first=False,
        question_budget=1,
        target_length=TargetLength(120, 220),
        required_sections=(
            "clinical_interpretation",
            "plain_language_explanation",
            "mechanism",
            "calibrated_reassurance" if reassurance.allowed else "uncertainty_boundary",
            "next_action",
        ),
    )
