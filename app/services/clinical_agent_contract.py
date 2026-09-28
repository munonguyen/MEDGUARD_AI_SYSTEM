"""Structured clinical contract for the V12 agent-first response path.

The deterministic stack owns facts, safety floors, red flags and tool results.
The agent stack owns clinical explanation and patient-facing prose.  This module
bridges the two without passing legacy deterministic prose to the writer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.chat import ChatIntent


@dataclass(frozen=True)
class ClinicalAgentContract:
    envelope: dict[str, Any]
    claims: list[dict[str, Any]]


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _safe_patient_context(context: dict[str, Any] | None) -> dict[str, Any]:
    source = context or {}
    # Patient identifiers and previous generated answer state must never become
    # medical evidence for the writer.
    allowed = ("age", "sex", "current_medications", "allergies", "conditions")
    return {key: source.get(key) for key in allowed if source.get(key) not in (None, [], "")}


def _questions(result: dict[str, Any]) -> list[str]:
    values = result.get("clarifying_questions") or result.get("guidance_questions") or []
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()][:3]


def build_clinical_agent_contract(
    *,
    intent: ChatIntent,
    question: str,
    clinical_result: dict[str, Any] | None,
    patient_context: dict[str, Any] | None = None,
) -> ClinicalAgentContract:
    result = dict(clinical_result or {})
    claims: list[dict[str, Any]] = []

    def add(category: str, text: str, *, required: bool = True, locked: bool = False) -> None:
        value = text.strip()
        if not value:
            return
        claims.append(
            {
                "id": f"{category}_{len(claims) + 1}",
                "category": category,
                "text": value,
                "required": required,
                "locked": locked,
            }
        )

    urgency = _text(result.get("urgency") or result.get("escalation_level") or "ROUTINE").upper()
    if intent == "triage":
        add("summary", f"Mức xử trí tối thiểu đã được hệ thống an toàn xác định: {urgency}.")

        specialty = result.get("recommended_specialty")
        if isinstance(specialty, dict):
            label = _text(specialty.get("label"))
            if label:
                add("finding", f"Hướng chuyên khoa hiện tại: {label}.", required=False)

        red_flags = result.get("red_flags") or []
        if isinstance(red_flags, list):
            for flag in red_flags[:6]:
                add("finding", f"Dấu hiệu đã được xác nhận từ bệnh cảnh hiện tại: {_text(flag)}.")

        if urgency == "EMERGENCY" or bool(result.get("emergency_flag")):
            # This is a safety constraint, not a response template. The writer
            # may explain around it but must preserve the immediate action.
            add(
                "action",
                "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức; không tự lái xe và không trì hoãn để tiếp tục hỏi trực tuyến.",
                locked=True,
            )
            add(
                "safety",
                "Không được hạ mức xử trí cấp cứu chỉ vì triệu chứng tạm thời giảm hoặc người bệnh muốn ở nhà theo dõi.",
                locked=False,
            )
        else:
            advice = _text(result.get("advice"))
            if advice:
                add("action", advice, required=False)

        for value in _questions(result):
            add("question", value, required=False)

    elif intent == "safety":
        risk = _text(result.get("overall_risk") or result.get("risk_level") or result.get("severity"))
        if risk:
            add("summary", f"Mức nguy cơ an toàn thuốc hiện tại: {risk}.")
        for key in ("warnings", "alerts", "recommendations", "actions"):
            values = result.get(key) or []
            if isinstance(values, list):
                for value in values[:6]:
                    if isinstance(value, dict):
                        message = _text(value.get("message") or value.get("text") or value.get("recommendation"))
                    else:
                        message = _text(value)
                    if message:
                        add("safety", message, required=True, locked=False)

    envelope = {
        "version": "v12-agent-first",
        "intent": intent,
        "user_question": question,
        "clinical_result": result,
        "patient_context": _safe_patient_context(patient_context),
        "communication_contract": {
            "compose_original_response": True,
            "legacy_template_prose_is_not_evidence": True,
            "directly_answer_main_concern_first": True,
            "detect_and_correct_dangerous_misconceptions": True,
            "explain_mechanism_in_plain_language_only_when_supported": True,
            "separate_assessment_from_diagnosis": True,
            "give_concrete_next_action": True,
            "avoid_generic_non_answers": True,
            "question_budget": 0 if urgency == "EMERGENCY" else 1,
            "emergency_action_precedes_explanation": urgency == "EMERGENCY",
        },
        # Derived from the supplied human doctor-response dataset as behavioral
        # principles only. They are not medical facts and never select canned
        # text by keyword.
        "professional_response_principles": [
            "Address the patient's actual concern before background explanation.",
            "If the patient proposes a dangerous action, interrupt and correct it before explaining why.",
            "Explain the clinical mechanism in everyday language only when the evidence supports it.",
            "Give a specific action plan and a clear threshold for seeking care.",
            "Ask only the single highest-information follow-up question when it can change management.",
            "Do not reuse fixed response templates or infer patient facts from rule antecedents.",
        ],
    }
    return ClinicalAgentContract(envelope=envelope, claims=claims)
