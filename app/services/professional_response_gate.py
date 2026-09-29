"""Deterministic non-authoring patient-response release gate.

V26 formalizes this layer as the Jev output-quality arbiter.  Jev does not
compose patient prose, diagnose, infer a new severity, or override deterministic
clinical authority.  It receives an already resolved response and can only
APPROVE it or request REVISION from the Writer/Reviewer loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal


_GENERIC_OPENINGS = (
    "thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu",
    "cần thêm đánh giá lâm sàng toàn diện",
    "không thể đưa ra bất kỳ nhận định nào",
)

_INTERNAL_JARGON = (
    "clinical envelope",
    "safety kernel",
    "model tier",
    "routing decision",
    "deterministic fallback",
    "jev",
    "kev",
    "writer agent",
    "reviewer agent",
)

_ACTION_MARKERS = (
    "gọi 115",
    "cấp cứu",
    "đến ",
    "đi khám",
    "khám ",
    "liên hệ",
    "ngừng ",
    "dừng ",
    "tránh ",
    "không dùng",
    "theo dõi",
    "rửa ",
    "uống ",
    "chườm ",
    "nghỉ ",
    "kiểm tra",
    "trao đổi",
    "nhờ người",
    "hãy ",
    "nên ",
)

_EMERGENCY_ACTION_MARKERS = (
    "gọi 115",
    "đến khoa cấp cứu",
    "đi cấp cứu",
    "cấp cứu gần nhất",
)

_FALSE_REASSURANCE = (
    "chắc chắn không nguy hiểm",
    "hoàn toàn không nguy hiểm",
    "chỉ cần theo dõi tại nhà",
    "không cần đi viện",
)

_DIAGNOSTIC_OVERCLAIM = (
    "chắc chắn là",
    "khẳng định bạn bị",
    "chắc chắn bạn bị",
)

_UNCERTAINTY_MARKERS = (
    "chưa đủ",
    "không thể xác định",
    "không thể khẳng định",
    "chưa thể xác định",
    "với thông tin hiện có",
    "dựa trên thông tin hiện có",
    "cần thêm thông tin",
    "không thay thế chẩn đoán",
    # Probabilistic pattern language is also calibrated uncertainty.  It is
    # intentionally narrower than generic words such as "có thể" so Jev does
    # not reward vague hedging that adds no clinical information.
    "thường phù hợp với",
    "phù hợp hơn là",
)


@dataclass(frozen=True)
class ProfessionalResponseAssessment:
    passed: bool
    score: float
    directness: float
    actionability: float
    safety: float
    professionalism: float
    reasons: tuple[str, ...]
    calibrated_uncertainty: float = 1.0
    question_policy: float = 1.0
    completeness: float = 1.0
    decision: Literal["approve", "revise"] = "approve"


def evaluate_professional_response(
    *,
    narrative_blocks: Iterable[str],
    urgency: str | None,
    locked_claims: Iterable[str] = (),
) -> ProfessionalResponseAssessment:
    """Score an already-authored response without authoring or changing severity.

    The function is intentionally deterministic.  Its only release decisions are
    ``approve`` and ``revise``; revision is performed by the Writer under the
    existing bounded loop.  Clinical urgency is read-only input.
    """
    blocks = [str(block).strip() for block in narrative_blocks if str(block).strip()]
    text = "\n".join(blocks)
    normalized = text.lower()
    first = (blocks[0] if blocks else "").lower()
    resolved_urgency = str(urgency or "").upper()
    clinical_response = resolved_urgency in {"ROUTINE", "URGENT", "EMERGENCY"}
    reasons: list[str] = []

    directness = 1.0
    if not blocks:
        directness = 0.0
        reasons.append("empty_response")
    elif any(phrase in first for phrase in _GENERIC_OPENINGS):
        directness = 0.0
        reasons.append("generic_opening")

    actionability = 1.0
    has_action = any(marker in normalized for marker in _ACTION_MARKERS)
    if clinical_response and not has_action:
        actionability = 0.0
        reasons.append("missing_action")

    safety = 1.0
    if any(phrase in normalized for phrase in _FALSE_REASSURANCE):
        safety = 0.0
        reasons.append("false_reassurance")
    if any(phrase in normalized for phrase in _DIAGNOSTIC_OVERCLAIM):
        safety = 0.0
        reasons.append("diagnostic_overclaim")

    locked = [str(value).strip() for value in locked_claims if str(value).strip()]
    if any(value not in text for value in locked):
        safety = 0.0
        reasons.append("missing_locked_claim")

    question_count = text.count("?")
    question_policy = 1.0
    if resolved_urgency == "EMERGENCY":
        # Emergency action must be in the first patient-facing block.  Jev may
        # reject ordering, but it never invents the action or changes urgency.
        if not any(marker in first for marker in _EMERGENCY_ACTION_MARKERS):
            safety = 0.0
            reasons.append("emergency_action_not_first")
        if question_count:
            safety = 0.0
            question_policy = 0.0
            reasons.append("emergency_followup_question")
        if "theo dõi tại nhà" in normalized or "đợi xem" in normalized:
            safety = 0.0
            reasons.append("emergency_delay_language")
    elif question_count > 1:
        # Multiple questions are not a hard safety failure, but they usually
        # indicate the Writer did not select the single highest-information ask.
        question_policy = 0.5
        reasons.append("too_many_followup_questions")

    professionalism = 1.0
    if any(term in normalized for term in _INTERNAL_JARGON):
        professionalism = 0.0
        reasons.append("internal_jargon_leak")

    calibrated_uncertainty = 1.0
    if clinical_response and not any(marker in normalized for marker in _UNCERTAINTY_MARKERS):
        calibrated_uncertainty = 0.5
        reasons.append("missing_calibrated_uncertainty")

    completeness = 1.0
    if clinical_response and not blocks:
        completeness = 0.0
    elif clinical_response and not has_action:
        completeness = 0.5
    elif resolved_urgency == "EMERGENCY" and not any(
        marker in first for marker in _EMERGENCY_ACTION_MARKERS
    ):
        completeness = 0.0

    score = round(
        0.18 * directness
        + 0.20 * actionability
        + 0.25 * safety
        + 0.12 * professionalism
        + 0.10 * calibrated_uncertainty
        + 0.08 * question_policy
        + 0.07 * completeness,
        4,
    )

    passed = (
        safety == 1.0
        and directness == 1.0
        and professionalism == 1.0
        and (not clinical_response or actionability == 1.0)
        and (resolved_urgency != "EMERGENCY" or question_policy == 1.0)
        and score >= 0.85
    )
    return ProfessionalResponseAssessment(
        passed=passed,
        score=score,
        directness=directness,
        actionability=actionability,
        safety=safety,
        professionalism=professionalism,
        reasons=tuple(dict.fromkeys(reasons)),
        calibrated_uncertainty=calibrated_uncertainty,
        question_policy=question_policy,
        completeness=completeness,
        decision="approve" if passed else "revise",
    )


# Explicit V26 name for architecture/docs while preserving the existing public
# function used by the agent graph and older tests.
evaluate_jev_release = evaluate_professional_response
