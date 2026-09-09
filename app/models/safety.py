from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.common import DisclaimerMixin, Status, Trace


class Allergy(BaseModel):
    substance: str
    reaction: str | None = None
    severity: Literal["LOW", "MODERATE", "HIGH"] | None = None


class MedicationItem(BaseModel):
    name: str
    active_ingredient: str | None = None
    dose_mg: float | None = None


class SafetyRequest(BaseModel):
    patient_ref: str = Field(min_length=1, max_length=128)
    age: int | None = None
    sex: Literal["male", "female", "other"] | None = None
    pregnancy_status: str | None = None
    renal_function: dict[str, float] | None = None
    allergies: list[Allergy] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    current_medications: list[MedicationItem] = Field(default_factory=list)
    proposed_medications: list[MedicationItem] = Field(default_factory=list)

    @field_validator("patient_ref")
    @classmethod
    def patient_ref_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("patient_ref must not be blank")
        return value


class SafetyWarning(BaseModel):
    type: str
    severity: Literal["LOW", "MODERATE", "HIGH"]
    tier: Literal["HARD_STOP", "SOFT_STOP"] | None = None
    medication: str | None = None
    interaction_id: str | None = None
    allergy_group: str | None = None
    detail: str
    clinical_consequence: str | None = None
    recommendation: str | None = None
    evidence_level: str | None = None
    matched_conditions: list[str] = Field(default_factory=list)
    basis: Literal["structured_table", "llm_explanation"]
    confidence: float


class SafetyResponse(DisclaimerMixin):
    request_id: str
    status: Status = Status.ok
    overall_risk: Literal["LOW", "MODERATE", "HIGH"]
    requires_human_review: bool
    warnings: list[SafetyWarning] = Field(default_factory=list)
    unknown_ingredients: list[str] = Field(default_factory=list)
    trace: Trace
