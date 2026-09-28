from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class ClinicalTask(str, Enum):
    ACUTE_SYMPTOM = "acute_symptom"
    MEDICATION_SAFETY = "medication_safety"
    LAB_INTERPRETATION = "lab_interpretation"
    EXPOSURE_REACTION = "exposure_reaction"
    CHRONIC_CONDITION = "chronic_condition"
    SELF_CARE = "self_care"
    MONITORING = "monitoring"
    FOLLOWUP = "followup"
    ADMINISTRATIVE = "administrative"
    GENERAL_MEDICAL = "general_medical"


class ClinicalTaskDecision(BaseModel):
    task: ClinicalTask
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    domain: str | None = None
