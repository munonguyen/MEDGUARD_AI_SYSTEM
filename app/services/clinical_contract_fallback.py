"""Deterministic V27.2 fallback composed from the same clinical contract as Writer.

This module is intentionally non-generative. It never invents a diagnosis or
new treatment claim. It only reshapes facts, reasoning, actions and questions
already present in ClinicalAgentContract and the deterministic Safety Kernel
answer so provider failures do not fall back to a one-size-fits-all template.
"""

from __future__ import annotations

import re
from typing import Any

from app.models.chat import GroundedAnswer
from app.services.clinical_agent_contract import ClinicalAgentContract


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _strings(values: Any, *, limit: int = 6) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _claims(contract: ClinicalAgentContract, category: str) -> list[str]:
    values: list[str] = []
    for claim in contract.claims:
        if _text(claim.get("category")) != category:
            continue
        text = _text(claim.get("text"))
        if text and text not in values:
            values.append(text)
    return values


def _append_unique(target: list[str], values: list[str]) -> None:
    for value in values:
        text = _text(value)
        if text and text not in target:
            target.append(text)


def _join_sentences(parts: list[str]) -> str:
    values: list[str] = []
    for raw in parts:
        text = raw.strip()
        if not text or text in values:
            continue
        if text[-1] not in ".?!":
            text += "."
        values.append(text)
    return " ".join(values)


def _format_medications(values: Any) -> str:
    if not isinstance(values, list):
        return ""
    names = [str(value).replace("_", " ").strip() for value in values if str(value).strip()]
    names = list(dict.fromkeys(names))
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " và " + names[-1]


def _safe_risk_sentence(value: Any) -> str:
    """Translate internal risk enums into bounded patient-facing language."""
    risk = _text(value).upper()
    return {
        "HIGH": "Có cảnh báo an toàn thuốc cần được ưu tiên xử lý trước khi dùng thêm hoặc phối hợp thuốc",
        "MODERATE": "Có yếu tố tương tác hoặc chưa chắc chắn cần được kiểm tra trước khi phối hợp thuốc",
        "LOW": "Chưa phát hiện cảnh báo mức cao trong phạm vi dữ liệu đã kiểm tra; điều này không khẳng định phối hợp thuốc là an toàn",
    }.get(risk, "")


def _first_warning_detail(result: dict[str, Any]) -> str:
    warnings = result.get("warnings")
    if not isinstance(warnings, list):
        return ""
    for warning in warnings:
        if not isinstance(warning, dict):
            continue
        detail = _text(warning.get("detail") or warning.get("message") or warning.get("text"))
        if detail:
            return detail
    return ""


def _current_turn_acknowledgement(envelope: dict[str, Any]) -> str:
    """Return a bounded current-turn sentence for multi-turn continuity.

    This is not free-form summarisation. It quotes only the current-turn text
    already supplied by the user, capped to one short sentence, so deterministic
    fallback visibly responds to what changed instead of repeating the previous
    turn verbatim.
    """
    episode = envelope.get("clinical_episode")
    if not isinstance(episode, dict):
        return ""
    try:
        turns = int(episode.get("user_turns_in_active_episode") or 1)
    except Exception:
        turns = 1
    if turns <= 1:
        return ""

    latest = _text(episode.get("latest_user_message"))
    if not latest:
        return ""
    marker = "lượt hiện tại:"
    lowered = latest.lower()
    if marker in lowered:
        latest = latest[lowered.rfind(marker) + len(marker):].strip()
    else:
        lines = [value.strip() for value in latest.splitlines() if value.strip()]
        latest = lines[-1] if lines else latest
    latest = re.sub(r"\s+", " ", latest).strip()
    if not latest or len(latest) > 220:
        latest = latest[:217].rstrip() + "..."
    latest = re.sub(r"^(?:tôi|mình)\b", "Bạn", latest, flags=re.I)
    latest = latest.rstrip("?.! ")
    if not latest:
        return ""
    return f"Điểm mới ở lượt này: {latest}"


def compose_contract_fallback(
    answer: GroundedAnswer,
    contract: ClinicalAgentContract,
) -> GroundedAnswer:
    """Return a context-aware deterministic fallback for clinical agent failure.

    Safety is monotonic: the response-policy layer may improve explanation,
    ordering and readability, but it must never remove a Safety Kernel/domain
    action already emitted before the provider call failed.
    """

    envelope = contract.envelope
    policy = envelope.get("response_policy") if isinstance(envelope.get("response_policy"), dict) else {}
    explanation = envelope.get("explanation_frame") if isinstance(envelope.get("explanation_frame"), dict) else {}
    result = envelope.get("clinical_result") if isinstance(envelope.get("clinical_result"), dict) else {}
    safety = envelope.get("safety_constraints") if isinstance(envelope.get("safety_constraints"), dict) else {}
    intent = _text(envelope.get("intent"))

    urgency = _text(safety.get("urgency_floor") or result.get("urgency") or "ROUTINE").upper()
    goal = _text(policy.get("communication_goal"))
    question_budget = int(policy.get("question_budget") or 0)
    current_turn = _current_turn_acknowledgement(envelope)

    what_it_may_mean = _text(explanation.get("what_it_may_mean"))
    mechanism = _text(explanation.get("mechanism"))
    uncertainty = _text(explanation.get("uncertainty"))
    why = _strings(explanation.get("why"), limit=4)

    reassurance = policy.get("reassurance") if isinstance(policy.get("reassurance"), dict) else {}
    reassurance_allowed = bool(reassurance.get("allowed"))
    reassurance_basis = _strings(reassurance.get("basis"), limit=3)
    reassurance_limits = _strings(reassurance.get("limitations"), limit=2)

    actions = _claims(contract, "action")
    safety_notes = _claims(contract, "safety")
    questions = _claims(contract, "question")
    findings = _claims(contract, "finding")

    _append_unique(actions, [str(value) for value in answer.next_steps])
    _append_unique(safety_notes, [str(value) for value in answer.safety_notes])
    _append_unique(findings, [str(value) for value in answer.key_points])

    for value in _strings(result.get("self_care"), limit=4):
        if value not in actions:
            actions.append(value)
    advice = _text(result.get("advice"))
    if advice and advice not in actions:
        actions.append(advice)

    if not questions and question_budget > 0:
        next_question = _text(explanation.get("next_best_question"))
        if next_question:
            questions.append(next_question)
    if not questions and question_budget > 0:
        _append_unique(questions, [str(value) for value in answer.questions])
    questions = questions[:question_budget]

    if urgency == "EMERGENCY":
        title = "Bạn cần được đánh giá cấp cứu ngay"
        emergency_action = next(
            (
                value
                for value in actions
                if any(marker in value.lower() for marker in ("115", "cấp cứu", "cap cuu"))
            ),
            actions[0] if actions else "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức; không tự lái xe.",
        )
        summary_parts = [emergency_action]
        if current_turn:
            summary_parts.append(current_turn)
        if what_it_may_mean:
            summary_parts.append(what_it_may_mean)
        elif findings:
            summary_parts.append("Các dấu hiệu hiện tại nằm trong nhóm cảnh báo cần xử trí cấp cứu")
        if mechanism:
            summary_parts.append(mechanism)
        if uncertainty:
            summary_parts.append(uncertainty)
        return answer.model_copy(
            update={
                "title": title,
                "summary": _join_sentences(summary_parts),
                "key_points": list(dict.fromkeys([*findings, *why]))[:6],
                "clinical_hypotheses": [],
                "next_steps": list(dict.fromkeys(actions))[:6],
                "safety_notes": list(dict.fromkeys(safety_notes))[:5],
                "questions": [],
                "display_questions": [],
            }
        )

    # Medication safety has no triage reasoning frame, so falling back to the
    # contract's generic summary claim used to expose internal HIGH/MODERATE/LOW
    # enums and erase the medicines already known from conversation memory.
    # Compose directly from the same bounded safety result instead.
    if intent == "safety":
        current_meds = _format_medications(result.get("conversation_current_medications"))
        proposed_meds = _format_medications(result.get("conversation_proposed_medications"))
        medication_context = ""
        if current_meds and proposed_meds:
            medication_context = f"Bạn đang dùng {current_meds} và đang cân nhắc {proposed_meds}"
        elif proposed_meds:
            medication_context = f"Thuốc đang được cân nhắc là {proposed_meds}"
        elif current_meds:
            medication_context = f"Các thuốc đang dùng được ghi nhận gồm {current_meds}"

        risk_sentence = _safe_risk_sentence(
            result.get("overall_risk") or result.get("risk_level") or result.get("severity")
        )
        warning_detail = _first_warning_detail(result)
        summary_parts = [value for value in (medication_context, risk_sentence, warning_detail) if value]
        if not summary_parts:
            existing = _text(answer.summary)
            if existing:
                summary_parts.append(existing)
            else:
                summary_parts.append("Cần kiểm tra thêm dữ kiện thuốc trước khi xác nhận cách phối hợp an toàn")

        risk = _text(result.get("overall_risk") or result.get("risk_level") or result.get("severity")).upper()
        title = {
            "HIGH": "Có cảnh báo an toàn thuốc cần ưu tiên xử lý",
            "MODERATE": "Cần kiểm tra trước khi phối hợp thuốc",
            "LOW": "Kết quả kiểm tra an toàn thuốc",
        }.get(risk, "Kết quả kiểm tra an toàn thuốc")
        limitations = list(answer.limitations)
        return answer.model_copy(
            update={
                "title": title,
                "summary": _join_sentences(summary_parts[:3]),
                "clinical_hypotheses": [],
                "next_steps": list(dict.fromkeys(actions))[:6],
                "safety_notes": list(dict.fromkeys(safety_notes))[:5],
                "questions": questions,
                "display_questions": questions,
                "limitations": limitations[:3],
            }
        )

    if urgency == "URGENT":
        title = "Bạn nên được đánh giá y tế sớm"
    elif goal == "clarify_uncertainty":
        title = "Cần thêm một thông tin quan trọng để định hướng chính xác hơn"
    elif goal == "reassure_and_guide":
        title = "Đặc điểm hiện tại giúp thu hẹp nguyên nhân"
    elif goal == "educate":
        title = "Giải thích ngắn gọn"
    else:
        title = "Giải thích triệu chứng hiện tại"

    summary_parts: list[str] = []
    if current_turn:
        summary_parts.append(current_turn)
    if what_it_may_mean:
        summary_parts.append(what_it_may_mean)
    if mechanism:
        summary_parts.append(mechanism)

    if reassurance_allowed:
        if reassurance_basis:
            summary_parts.append(
                "Những đặc điểm hiện có làm khả năng tình trạng nguy hiểm thấp hơn so với khi có các dấu hiệu cảnh báo"
            )
        summary_parts.extend(reassurance_limits)
    elif uncertainty:
        summary_parts.append(uncertainty)

    if not summary_parts:
        summary_claims = _claims(contract, "summary")
        summary_parts.extend(summary_claims)
    if not summary_parts:
        existing_summary = _text(answer.summary)
        if existing_summary:
            summary_parts.append(existing_summary)
        else:
            summary_parts.append("Thông tin hiện có chưa đủ để đưa ra nhận định chắc chắn")

    key_points = list(dict.fromkeys([*why, *findings, *reassurance_basis]))[:6]
    limitations = list(answer.limitations)
    if uncertainty and uncertainty not in limitations:
        limitations.insert(0, uncertainty)

    return answer.model_copy(
        update={
            "title": title,
            "summary": _join_sentences(summary_parts),
            "key_points": key_points,
            "clinical_hypotheses": [],
            "next_steps": list(dict.fromkeys(actions))[:6],
            "safety_notes": list(dict.fromkeys(safety_notes))[:5],
            "questions": questions,
            "display_questions": questions,
            "limitations": limitations[:3],
        }
    )