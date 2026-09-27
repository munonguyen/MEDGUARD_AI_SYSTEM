"""Deterministic clinical dialogue policy for selecting clarifying questions.

The policy never diagnoses, changes triage, or invents clinical facts. It only
ranks already-approved question candidates produced by clinical rules/guidance.
This keeps keyword/phrase matching in a routing role instead of allowing it to
control patient-facing clinical conclusions.
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
    "hay la",
)

_PERSONALIZATION_MARKERS = (
    "cong viec",
    "thoi quen",
    "muc tieu",
    "ban muon",
)

_BASE_SCORE: dict[QuestionCategory, float] = {
    "SAFETY": 80.0,
    "DISPOSITION": 76.0,
    "TREATMENT_SAFETY": 84.0,
    "CONTRADICTION": 88.0,
    "DIAGNOSTIC": 55.0,
    "PERSONALIZATION": 35.0,
}


def _question_id(normalized_question: str) -> str:
    digest = sha1(normalized_question.encode("utf-8")).hexdigest()[:10]
    return f"Q-{digest}"


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _classify(question: str) -> tuple[QuestionCategory, bool, list[str]]:
    normalized = normalize_search_text(question)
    reasons: list[str] = []

    if _contains_any(normalized, _CONTRADICTION_MARKERS):
        reasons.append("resolves_contradiction")
        return "CONTRADICTION", True, reasons
    if _contains_any(normalized, _TREATMENT_SAFETY_MARKERS):
        reasons.append("treatment_safety_impact")
        return "TREATMENT_SAFETY", True, reasons
    if _contains_any(normalized, _SAFETY_MARKERS):
        reasons.append("potential_safety_impact")
        return "SAFETY", True, reasons
    if _contains_any(normalized, _DISPOSITION_MARKERS):
        reasons.append("can_change_disposition")
        return "DISPOSITION", False, reasons
    if _contains_any(normalized, _PERSONALIZATION_MARKERS):
        reasons.append("personalization_only")
        return "PERSONALIZATION", False, reasons

    reasons.append("diagnostic_refinement")
    return "DIAGNOSTIC", False, reasons


def _score_question(
    text: str,
    category: QuestionCategory,
    *,
    urgency: str,
    mandatory: bool,
) -> tuple[float, list[str]]:
    score = _BASE_SCORE[category]
    reasons: list[str] = []
    normalized = normalize_search_text(text)

    if urgency == "URGENT":
        if category == "SAFETY":
            score += 15.0
            reasons.append("urgent_safety_priority")
        elif category == "DISPOSITION":
            score += 10.0
            reasons.append("urgent_disposition_priority")
    elif urgency == "ROUTINE":
        if category == "DISPOSITION":
            score += 6.0
            reasons.append("routine_information_gain")
        elif category == "SAFETY":
            # Routine answers already contain a safety-net. A safety question is
            # useful, but should not automatically crowd out the next question
            # that most improves the current decision.
            score -= 20.0
            reasons.append("routine_safety_net_already_present")

    if mandatory:
        score += 5.0

    # Prefer concise, single-purpose questions. Multi-clause intake forms are
    # intentionally penalized because they increase user burden and reduce
    # answer quality in conversational use.
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
    """Rank approved clarifying questions by expected clinical utility.

    Invariants:
    - EMERGENCY never waits for a clarifying question.
    - ROUTINE normally asks at most one high-value question per turn.
    - URGENT may ask at most two questions, with safety/disposition first.
    - Duplicate questions are removed before scoring.
    - This function does not create new clinical questions.
    """
    urgency = urgency.upper().strip()
    if urgency == "EMERGENCY":
        return QuestionPlan(selected=(), candidate_count=len(questions), dropped_count=len(questions), max_questions=0)

    if max_questions is None:
        max_questions = 2 if urgency == "URGENT" else 1
    max_questions = max(0, min(max_questions, 2))

    deduped: list[str] = []
    seen: set[str] = set()
    for raw in questions:
        text = raw.strip()
        if not text:
            continue
        normalized = normalize_search_text(text)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(text)

    candidates: list[QuestionCandidate] = []
    for text in deduped:
        normalized = normalize_search_text(text)
        category, mandatory, classification_reasons = _classify(text)
        score, score_reasons = _score_question(
            text,
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
        key=lambda candidate: (
            candidate.score,
            candidate.mandatory,
            -len(candidate.text),
        ),
        reverse=True,
    )

    selected: list[QuestionCandidate] = []
    selected_categories: set[QuestionCategory] = set()
    for candidate in ranked:
        if len(selected) >= max_questions:
            break
        if selected and candidate.category in selected_categories:
            # Prefer a second question that adds a different kind of information.
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
