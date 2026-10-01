from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CommunicationGoal(str, Enum):
    EDUCATE = "educate"
    EXPLAIN_SYMPTOM = "explain_symptom"
    REASSURE_AND_GUIDE = "reassure_and_guide"
    CLARIFY_UNCERTAINTY = "clarify_uncertainty"
    URGENT_GUIDANCE = "urgent_guidance"
    EMERGENCY_ACTION = "emergency_action"
    MEDICATION_EDUCATION = "medication_education"
    MEDICATION_SAFETY = "medication_safety"


class ResponseDepth(str, Enum):
    D1_DIRECT = "D1_DIRECT"
    D2_EXPLAIN = "D2_EXPLAIN"
    D3_CLINICAL_GUIDANCE = "D3_CLINICAL_GUIDANCE"
    D4_URGENT = "D4_URGENT"
    D5_EMERGENCY = "D5_EMERGENCY"


@dataclass(frozen=True)
class ReassurancePolicy:
    allowed: bool
    strength: str = "none"
    basis: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "strength": self.strength,
            "basis": list(self.basis),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class TargetLength:
    min_words: int
    max_words: int

    def to_payload(self) -> dict[str, int]:
        return {"min_words": self.min_words, "max_words": self.max_words}


@dataclass(frozen=True)
class ClinicalResponsePolicy:
    communication_goal: CommunicationGoal
    response_depth: ResponseDepth
    explanation_required: bool
    mechanism_required: bool
    reassurance: ReassurancePolicy
    action_first: bool
    question_budget: int
    target_length: TargetLength
    required_sections: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "communication_goal": self.communication_goal.value,
            "response_depth": self.response_depth.value,
            "explanation_required": self.explanation_required,
            "mechanism_required": self.mechanism_required,
            "reassurance": self.reassurance.to_payload(),
            "action_first": self.action_first,
            "question_budget": self.question_budget,
            "target_length": self.target_length.to_payload(),
            "required_sections": list(self.required_sections),
        }
