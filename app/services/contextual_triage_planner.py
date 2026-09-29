"""Deterministic V25 response planning for triage fallback paths.

The live Writer receives the same episode/reasoning structures through the
ClinicalAgentContract. This module gives deterministic/offline execution the
same reasoning shape so benchmark quality does not depend on model access.

It never changes urgency, ESI, specialty, red flags, safety-net instructions or
locked emergency actions. It may only improve explanation, hypothesis ordering
and ranking of follow-up questions for non-emergency cases.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.clinical_episode import ClinicalEpisodeModel
from app.models.clinical_reasoning import ClinicalReasoningFrame, MechanismHypothesis
from app.services.clinical_episode_model import build_clinical_episode_model
from app.services.clinical_text import normalize_search_text
from app.services.contextual_clinical_reasoner import build_contextual_reasoning_frame


@dataclass(frozen=True)
class ContextualTriagePlan:
    summary: str | None
    hypotheses: tuple[str, ...]
    # Keep the full approved candidate set for audit/evaluation. The existing
    # ChatResponse question policy decides what the patient actually sees.
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


def _mechanism_has_direct_narrative_support(
    item: MechanismHypothesis,
    episode: ClinicalEpisodeModel,
) -> bool:
    """Require direct trigger evidence before deterministic prose is replaced.

    The underlying reasoner intentionally has high recall. The deterministic
    renderer is stricter: a plausible mechanism can alter patient-facing prose
    only when its trigger is actually present in the user-authored episode.
    This prevents, for example, generic prolonged headache from being called a
    posture problem or nausea alone from being described as fluid loss.
    """
    text = normalize_search_text(episode.active_episode_text or episode.latest_user_message)
    if item.hypothesis_id == "visual_load_contribution":
        return any(marker in text for marker in (
            "man hinh", "may tinh", "laptop", "dien thoai", "hoc online",
        ))
    if item.hypothesis_id == "postural_pericranial_tension":
        return any(marker in text for marker in (
            "man hinh", "may tinh", "ngoi", "co vai", "vai gay", "tu the",
        ))
    if item.hypothesis_id == "headache_threshold_modifiers":
        return any(marker in text for marker in (
            "mat ngu", "thieu ngu", "ngu it", "thuc khuya", "it nuoc",
            "mat nuoc", "khat", "cang thang", "stress", "ap luc",
        ))
    if item.hypothesis_id == "fluid_loss_contribution":
        return any(marker in text for marker in (
            "tieu chay", "da non", "bi non", "non ra", "non mua",
            "khong giu duoc nuoc", "nôn ra", "đã nôn",
        ))
    if item.hypothesis_id == "mechanical_postural_load":
        return any(marker in text for marker in (
            "ngoi", "may tinh", "van phong", "tu the", "di lai thi",
            "dung day thi",
        ))
    # Other mechanisms are constructed from specific relations/exposures and
    # already require direct evidence in the reasoner.
    return True


def _explanatory_mechanisms(
    frame: ClinicalReasoningFrame,
    episode: ClinicalEpisodeModel,
) -> list[MechanismHypothesis]:
    """Return mechanisms supported enough to alter explanatory prose."""
    return [
        item for item in frame.mechanisms
        if item.role in {"leading", "contributor"}
        and bool(item.evidence_for)
        and _mechanism_has_direct_narrative_support(item, episode)
    ]


def _summary_from_frame(
    episode: ClinicalEpisodeModel,
    frame: ClinicalReasoningFrame,
    explanatory: list[MechanismHypothesis],
    *,
    urgency: str,
    existing_summary: str | None,
) -> str | None:
    if urgency == "EMERGENCY" or not explanatory:
        return existing_summary

    primary = explanatory[0]
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


def _merge_questions(
    preferred: str | None,
    existing_questions: list[str] | tuple[str, ...],
) -> tuple[str, ...]:
    """Preserve every approved candidate and place V25's preferred one first.

    The patient surface remains bounded downstream by ``question_policy``. This
    preserves backward-compatible audit data while allowing a higher-information
    V25 candidate to compete for display.
    """
    values: list[str] = []
    for raw in ([preferred] if preferred else []) + list(existing_questions):
        value = str(raw or "").strip()
        if value and value not in values:
            values.append(value)
    return tuple(values)


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
        # The current reasoner reads ``latest_user_message`` while extracting
        # trigger relations. Give it a temporary view of the full active episode
        # without corrupting the episode model's true latest-turn field.
        reasoning_episode = episode.model_copy(
            update={"latest_user_message": symptoms_text}
        )
        frame = build_contextual_reasoning_frame(
            reasoning_episode,
            urgency=normalized_urgency,
        )
    except Exception:
        return ContextualTriagePlan(
            summary=existing_summary,
            hypotheses=tuple(existing_hypotheses),
            questions=tuple(str(value) for value in existing_questions if str(value).strip()),
            episode=None,
            reasoning=None,
            applied=False,
            reason="contextual_reasoning_unavailable",
        )

    explanatory = _explanatory_mechanisms(frame, episode)
    if not explanatory:
        # Do not disturb established domain-specific guidance solely because an
        # unanswered red-flag slot exists. That slot remains available to the
        # agent contract, while deterministic output stays backward compatible.
        return ContextualTriagePlan(
            summary=existing_summary,
            hypotheses=tuple(str(value) for value in existing_hypotheses if str(value).strip()),
            questions=tuple(str(value) for value in existing_questions if str(value).strip()),
            episode=episode,
            reasoning=frame,
            applied=False,
            reason="no_supported_explanatory_mechanism",
        )

    contextual_hypotheses: list[str] = []
    for item in explanatory:
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

    questions = _merge_questions(frame.next_best_question, existing_questions)
    summary = _summary_from_frame(
        episode,
        frame,
        explanatory,
        urgency=normalized_urgency,
        existing_summary=existing_summary,
    )

    return ContextualTriagePlan(
        summary=summary,
        hypotheses=tuple(contextual_hypotheses),
        questions=questions,
        episode=episode,
        reasoning=frame,
        applied=True,
        reason="contextual_reasoning_applied",
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
        "leading_hypotheses": [item.hypothesis_id for item in explanatory_from_plan(plan)],
        "next_question_key": plan.reasoning.next_question_key,
    }


def explanatory_from_plan(plan: ContextualTriagePlan) -> list[MechanismHypothesis]:
    if plan.episode is None or plan.reasoning is None:
        return []
    return _explanatory_mechanisms(plan.reasoning, plan.episode)
