"""Deterministic clinical dialogue policy for selecting patient-facing questions.

The policy is deliberately downstream of clinical decision making. It never
changes triage, specialty, red flags, advice, evidence, or clinical facts. It
only ranks questions already produced by approved rules/guidance.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from typing import Literal

from app.services.clinical_text import normalize_search_text


QuestionCategory = Literal[
    "SAFETY",
    "DISPOSITION",
    "TREATMENT_SAFETY",
    "CONTRADICTION",
    "DIAGNOSTIC",
    "PERSONALIZATION",
]


@dataclass(frozen=True)
class QuestionCandidate:
    question_id: str
    text: str
    category: QuestionCategory
    score: float
    mandatory: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class QuestionPlan:
    selected: tuple[QuestionCandidate, ...]
    candidate_count: int
    dropped_count: int
    max_questions: int

    @property
    def questions(self) -> list[str]:
        return [candidate.text for candidate in self.selected]

    def trace_payload(self) -> dict[str, object]:
        return {
            "max_questions": self.max_questions,
            "candidate_count": self.candidate_count,
            "dropped_count": self.dropped_count,
            "selected": [
                {
                    "id": candidate.question_id,
                    "category": candidate.category,
                    "score": round(candidate.score, 2),
                    "mandatory": candidate.mandatory,
                    "reasons": list(candidate.reasons),
                }
                for candidate in self.selected
            ],
        }


_SAFETY_MARKERS = (
    "cap cuu",
    "ngat",
    "kho tho",
    "non ra mau",
    "phan den",
    "di ngoai ra mau",
    "bung cung",
    "bung chuong",
    "yeu liet",
    "yeu chan",
    "bi tieu",
    "mat kiem soat tieu",
    "te vung yen ngua",
    "te quanh hau mon",
    "meo mieng",
    "noi kho",
    "tim tai",
    "chay mau",
    "lan tay",
    "lan ham",
)

_DISPOSITION_MARKERS = (
    "0 den 10",
    "muc dau",
    "muc do dau",
    "dang tang nhanh",
    "bat dau tu khi nao",
    "bat dau luc nao",
    "bao lau",
    "lien tuc hay tung con",
    "di duoc",
    "chiu luc",
    "uong duoc nuoc",
    "giu duoc nuoc",
    "da non chua",
    "anh huong sinh hoat",
    "co the di lai",
)

_TREATMENT_SAFETY_MARKERS = (
    "thuoc",
    "lieu",
    "di ung",
    "mang thai",
    "cho con bu",
    "chong dong",
    "warfarin",
    "sintrom",
)

_CONTRADICTION_MARKERS = (
    "xac nhan lai",
    "thuc te",
    "noi nham",
    "dinh chinh",
    "y ban la",
)

_PERSONALIZATION_MARKERS = (
    "cong viec",
    "thoi quen",
    "muc tieu",
    "ban muon",
)

_SEVERITY_MARKERS = (
    "0 den 10",
    "muc dau",
    "muc do dau",
    "dang tang nhanh",
    "dau tang",
)

_FUNCTION_MARKERS = (
    "chiu luc",
    "di duoc",
    "co the di lai",
    "kho di",
    "khong di duoc",
)

_HYDRATION_MARKERS = (
    "da non chua",
    "uong duoc nuoc",
    "giu duoc nuoc",
    "non lien tuc",
)

_ONSET_MARKERS = (
    "bat dau tu khi nao",
    "bat dau luc nao",
    "bao lau",
    "lien tuc hay tung con",
)

_LOCALIZATION_MARKERS = (
    "vi tri nao",
    "o dau",
    "vung nao",
    "tren hay duoi bung",
    "tren ron",
    "quanh ron",
    "bap chan",
    "dui",
    "co chan",
)

_BASE_SCORE: dict[QuestionCategory, float] = {
    "SAFETY": 80.0,
    "DISPOSITION": 76.0,
    "TREATMENT_SAFETY": 90.0,
    "CONTRADICTION": 96.0,
    "DIAGNOSTIC": 55.0,
    "PERSONALIZATION": 35.0,
}


def _question_id(normalized_question: str) -> str:
    return f"Q-{sha1(normalized_question.encode('utf-8')).hexdigest()[:10]}"


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _classify(normalized: str) -> tuple[QuestionCategory, bool, list[str]]:
    if _contains_any(normalized, _CONTRADICTION_MARKERS):
        return "CONTRADICTION", True, ["resolves_contradiction"]
    if _contains_any(normalized, _TREATMENT_SAFETY_MARKERS):
        return "TREATMENT_SAFETY", True, ["treatment_safety_impact"]
    if _contains_any(normalized, _SAFETY_MARKERS):
        return "SAFETY", True, ["potential_safety_impact"]
    if _contains_any(normalized, _DISPOSITION_MARKERS):
        return "DISPOSITION", False, ["can_change_disposition"]
    if _contains_any(normalized, _PERSONALIZATION_MARKERS):
        return "PERSONALIZATION", False, ["personalization_only"]
    return "DIAGNOSTIC", False, ["diagnostic_refinement"]


def _score_question(
    text: str,
    normalized: str,
    category: QuestionCategory,
    *,
    urgency: str,
    mandatory: bool,
) -> tuple[float, list[str]]:
    score = _BASE_SCORE[category]
    reasons: list[str] = []

    # Safety questions dominate urgent decisions, but routine answers already
    # carry a full safety-net; in routine care, decision-changing information
    # should normally be asked before repeating every red flag.
    if urgency == "URGENT":
        if category == "SAFETY":
            score += 25.0
            reasons.append("urgent_safety_priority")
        elif category == "DISPOSITION":
            score += 10.0
            reasons.append("urgent_disposition_priority")
    elif urgency == "ROUTINE":
        if category == "DISPOSITION":
            score += 6.0
            reasons.append("routine_information_gain")
        elif category == "SAFETY":
            score -= 25.0
            reasons.append("routine_safety_net_already_present")

    # Information-gain bonuses. These are intentionally concept based rather
    # than disease-name based, so keywords route a question's purpose without
    # becoming a diagnosis or clinical conclusion.
    if _contains_any(normalized, _SEVERITY_MARKERS):
        score += 18.0
        reasons.append("severity_changes_disposition")
    if _contains_any(normalized, _FUNCTION_MARKERS):
        score += 18.0
        reasons.append("functional_status_changes_disposition")
    if _contains_any(normalized, _HYDRATION_MARKERS):
        score += 20.0
        reasons.append("hydration_or_vomiting_changes_disposition")
    if _contains_any(normalized, _LOCALIZATION_MARKERS):
        score += 8.0
        reasons.append("localization_information_gain")
    if _contains_any(normalized, _ONSET_MARKERS):
        score += 4.0
        reasons.append("timeline_information_gain")

    if mandatory:
        score += 5.0

    # Conversational burden penalty: prefer one answerable clinical decision
    # question over an intake-form sentence containing many unrelated clauses.
    if len(text) > 180:
        score -= 8.0
        reasons.append("long_question_penalty")
    elif len(text) > 120:
        score -= 4.0
        reasons.append("moderate_length_penalty")

    conjunctions = normalized.count(" va ") + normalized.count(" hoac ")
    if conjunctions >= 3:
        score -= 6.0
        reasons.append("multi_part_burden_penalty")
    elif conjunctions >= 2:
        score -= 3.0
        reasons.append("multi_part_burden_penalty")
    if text.count("?") > 1:
        score -= 4.0
        reasons.append("multiple_question_marks_penalty")

    return score, reasons


def plan_clinical_questions(
    questions: list[str],
    *,
    urgency: str,
    max_questions: int | None = None,
) -> QuestionPlan:
    """Select the smallest useful subset from an approved candidate set.

    Invariants:
    - EMERGENCY never waits for clarification.
    - ROUTINE displays at most one high-information question.
    - URGENT displays at most two questions, prioritizing safety/disposition.
    - No question is invented here; output is always a subset of input.
    - Candidate questions remain available upstream for audit/evaluation.
    """
    urgency = urgency.upper().strip()
    if urgency == "EMERGENCY":
        return QuestionPlan(
            selected=(),
            candidate_count=len(questions),
            dropped_count=len(questions),
            max_questions=0,
        )

    if max_questions is None:
        max_questions = 2 if urgency == "URGENT" else 1
    max_questions = max(0, min(max_questions, 2))

    deduped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in questions:
        text = raw.strip()
        if not text:
            continue
        normalized = normalize_search_text(text)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append((text, normalized))

    candidates: list[QuestionCandidate] = []
    for text, normalized in deduped:
        category, mandatory, classification_reasons = _classify(normalized)
        score, score_reasons = _score_question(
            text,
            normalized,
            category,
            urgency=urgency,
            mandatory=mandatory,
        )
        candidates.append(
            QuestionCandidate(
                question_id=_question_id(normalized),
                text=text,
                category=category,
                score=score,
                mandatory=mandatory,
                reasons=tuple(classification_reasons + score_reasons),
            )
        )

    ranked = sorted(
        candidates,
        key=lambda candidate: (candidate.score, candidate.mandatory, -len(candidate.text)),
        reverse=True,
    )

    selected: list[QuestionCandidate] = []
    selected_categories: set[QuestionCategory] = set()
    for candidate in ranked:
        if len(selected) >= max_questions:
            break
        if selected and candidate.category in selected_categories:
            alternative_exists = any(
                other.category not in selected_categories
                and other not in selected
                and other.score >= candidate.score - 8.0
                for other in ranked
            )
            if alternative_exists:
                continue
        selected.append(candidate)
        selected_categories.add(candidate.category)

    return QuestionPlan(
        selected=tuple(selected),
        candidate_count=len(candidates),
        dropped_count=max(0, len(candidates) - len(selected)),
        max_questions=max_questions,
    )
