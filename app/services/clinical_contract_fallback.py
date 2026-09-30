"""Deterministic V27.1 fallback composed from the same clinical contract as Writer.

This module is intentionally non-generative. It never invents a diagnosis or
new treatment claim. It only reshapes facts, reasoning, actions and questions
already present in ClinicalAgentContract and the deterministic Safety Kernel
answer so provider failures do not fall back to the legacy one-size-fits-all
triage template.
"""

from __future__ import annotations

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


def compose_contract_fallback(
    answer: GroundedAnswer,
    contract: ClinicalAgentContract,
) -> GroundedAnswer:
    """Return a context-aware deterministic fallback for clinical agent failure.

    Safety is monotonic here: V27.1 may improve explanation/title/ordering, but it
    must never remove an action or safety note already emitted by the underlying
    deterministic domain service. This is critical when a provider error happens
    after Safety Kernel/domain rules have already resolved an emergency action.
    """

    envelope = contract.envelope
    policy = envelope.get("response_policy") if isinstance(envelope.get("response_policy"), dict) else {}
    explanation = envelope.get("explanation_frame") if isinstance(envelope.get("explanation_frame"), dict) else {}
    result = envelope.get("clinical_result") if isinstance(envelope.get("clinical_result"), dict) else {}
    safety = envelope.get("safety_constraints") if isinstance(envelope.get("safety_constraints"), dict) else {}

    urgency = _text(safety.get("urgency_floor") or result.get("urgency") or "ROUTINE").upper()
    goal = _text(policy.get("communication_goal"))
    question_budget = int(policy.get("question_budget") or 0)

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

    # Safety-monotonic merge: domain/Safety Kernel actions remain authoritative.
    # The response-policy layer may add context, but never delete these fields.
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
        # Preserve an existing domain summary before resorting to a generic
        # uncertainty sentence. This is especially important for medication and
        # exposure branches whose deterministic result already carries the key
        # safety explanation.
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
