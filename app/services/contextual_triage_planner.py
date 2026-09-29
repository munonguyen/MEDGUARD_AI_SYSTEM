"""Deterministic V25 response planning for triage fallback paths.

The live Writer receives the same episode/reasoning structures through the
ClinicalAgentContract.  This module gives deterministic/offline execution the
same *reasoning shape* so benchmark quality does not depend on model access.

It never changes urgency, ESI, specialty, red flags, safety-net instructions or
locked emergency actions. It may only improve explanation, hypothesis ordering
and the one follow-up question shown for non-emergency cases.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.clinical_episode import ClinicalEpisodeModel
from app.models.clinical_reasoning import ClinicalReasoningFrame, MechanismHypothesis
from app.services.clinical_episode_model import build_clinical_episode_model
from app.services.contextual_clinical_reasoner import build_contextual_reasoning_frame


@dataclass(frozen=True)
class ContextualTriagePlan:
    summary: str | None
    hypotheses: tuple[str, ...]
    questions: tuple[str, ...]
    episode: ClinicalEpisodeModel | None
    reasoning: ClinicalReasoningFrame | None
    applied: bool
    reason: str


def _episode_messages(symptoms_text: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in symptoms_text.splitlines() if line.strip()]
    if not lines:
        lines = [symptoms_text.strip()]
    values: list[dict[str, str]] = []
    for line in lines:
        if line.lower().startswith("lượt hiện tại:"):
            line = line.split(":", 1)[1].strip()
        if line:
            values.append({"role": "user", "content": line})
    return values


def _patient_hypothesis(item: MechanismHypothesis) -> str:
    base = item.patient_safe_statement.strip()
    mechanism = item.mechanism.strip()
    if not mechanism:
        return base
    if base.endswith((".", "!", "?")):
        return f"{base} Cơ chế có thể góp phần: {mechanism}"
    return f"{base}. Cơ chế có thể góp phần: {mechanism}"


def _summary_from_frame(
    episode: ClinicalEpisodeModel,
    frame: ClinicalReasoningFrame,
    *,
    urgency: str,
    existing_summary: str | None,
) -> str | None:
    if urgency == "EMERGENCY":
        return existing_summary

    leading = [item for item in frame.mechanisms if item.role == "leading"]
    contributors = [item for item in frame.mechanisms if item.role == "contributor"]
    if not leading and not contributors:
        return existing_summary

    primary = (leading or contributors)[0]
    parts: list[str] = []

    if episode.user_turns_in_active_episode > 1:
        parts.append(
            "Các dữ kiện mới trong lượt này giúp điều chỉnh nhận định thay vì chỉ lặp lại đánh giá trước."
        )

    parts.append(primary.patient_safe_statement.strip())
    parts.append(primary.mechanism.strip())

    if frame.must_not_miss_unknowns:
        parts.append(
            "Một số dấu hiệu có thể làm thay đổi mức xử trí vẫn chưa được xác nhận; "
            "việc bạn chưa nhắc tới chúng được xem là chưa biết, không phải là đã âm tính."
        )

    parts.append(
        "Đây là giải thích làm việc dựa trên bệnh cảnh hiện có, không phải chẩn đoán xác định."
    )
    return " ".join(value for value in parts if value)


def build_contextual_triage_plan(
    *,
    symptoms_text: str,
    urgency: str,
    existing_summary: str | None = None,
    existing_hypotheses: list[str] | tuple[str, ...] = (),
    existing_questions: list[str] | tuple[str, ...] = (),
) -> ContextualTriagePlan:
    normalized_urgency = str(urgency).upper()
    if normalized_urgency == "EMERGENCY":
        # Emergency communication is action-first. Explanation enrichment is
        # deliberately disabled so it can never delay or dilute the action.
        return ContextualTriagePlan(
            summary=existing_summary,
            hypotheses=tuple(existing_hypotheses),
            questions=(),
            episode=None,
            reasoning=None,
            applied=False,
            reason="emergency_action_first",
        )

    try:
        messages = _episode_messages(symptoms_text)
        if not messages:
            raise ValueError("empty clinical narrative")
        episode = build_clinical_episode_model(
            episode_id="deterministic-active-episode",
            messages=messages,
        )
        episode = episode.model_copy(
            update={
                "active_episode_text": symptoms_text,
                "latest_user_message": messages[-1]["content"],
            }
        )
        frame = build_contextual_reasoning_frame(episode, urgency=normalized_urgency)
    except Exception:
        return ContextualTriagePlan(
            summary=existing_summary,
            hypotheses=tuple(existing_hypotheses),
            questions=tuple(existing_questions)[:1],
            episode=None,
            reasoning=None,
            applied=False,
            reason="contextual_reasoning_unavailable",
        )

    contextual_hypotheses: list[str] = []
    for item in frame.mechanisms:
        if item.role == "must_not_miss_pathway":
            continue
        value = _patient_hypothesis(item)
        if value and value not in contextual_hypotheses:
            contextual_hypotheses.append(value)
        if len(contextual_hypotheses) >= 3:
            break
    for value in existing_hypotheses:
        value = str(value).strip()
        if value and value not in contextual_hypotheses:
            contextual_hypotheses.append(value)
        if len(contextual_hypotheses) >= 4:
            break

    questions: tuple[str, ...]
    if frame.next_best_question:
        questions = (frame.next_best_question,)
    else:
        questions = tuple(str(value) for value in existing_questions if str(value).strip())[:1]

    summary = _summary_from_frame(
        episode,
        frame,
        urgency=normalized_urgency,
        existing_summary=existing_summary,
    )

    return ContextualTriagePlan(
        summary=summary,
        hypotheses=tuple(contextual_hypotheses),
        questions=questions,
        episode=episode,
        reasoning=frame,
        applied=bool(frame.mechanisms or frame.next_best_question),
        reason="contextual_reasoning_applied" if (frame.mechanisms or frame.next_best_question) else "no_contextual_signal",
    )


def reasoning_trace_payload(plan: ContextualTriagePlan) -> dict[str, Any]:
    if plan.episode is None or plan.reasoning is None:
        return {"applied": plan.applied, "reason": plan.reason}
    return {
        "applied": plan.applied,
        "reason": plan.reason,
        "episode_version": plan.episode.version,
        "reasoning_version": plan.reasoning.version,
        "chief_domain": plan.episode.chief_domain,
        "user_turns": plan.episode.user_turns_in_active_episode,
        "delta": plan.episode.delta.model_dump(mode="json"),
        "historical_risk": [fact.concept for fact in plan.episode.historical_risk],
        "unknown_decision_relevant": [item.key for item in plan.episode.unknown_decision_relevant],
        "leading_hypotheses": list(plan.reasoning.leading_hypothesis_ids),
        "next_question_key": plan.reasoning.next_question_key,
    }
