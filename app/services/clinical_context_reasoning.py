"""Clinical context reasoning primitives for MedGuard V28.1.

A symptom word alone is not a triage decision. This layer separates finding
extraction from risk evaluation.
"""

from dataclasses import dataclass
from enum import Enum
import re


class RiskLevel(str, Enum):
    ROUTINE = "ROUTINE"
    URGENT = "URGENT"
    EMERGENCY = "EMERGENCY"


@dataclass(frozen=True)
class ClinicalFinding:
    symptom: str
    present: bool
    confidence: float


_NEGATION = r"(?:khong|chua|khong co|khong bi|khong thay)"


def is_negated(text: str, keyword: str) -> bool:
    pattern = rf"{_NEGATION}\s+(?:\w+\s+){{0,3}}{re.escape(keyword)}"
    return bool(re.search(pattern, text.lower()))


def classify_pain_context(onset: str, associated: list[str]) -> RiskLevel:
    high_risk = {
        "sudden_maximal",
        "loss_of_consciousness",
        "new_neurological_deficit",
        "severe_breathing_problem",
    }
    if onset in high_risk or any(item in high_risk for item in associated):
        return RiskLevel.EMERGENCY
    return RiskLevel.ROUTINE
