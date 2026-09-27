from __future__ import annotations

from typing import Any, Literal

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


class SafetyKernelResult(BaseModel):
    """Deterministic Safety Kernel result running independently before reasoning."""
    emergency_lock: bool = Field(default=False, description="Hard lock on emergency care; cannot be downgraded by LLMs")
    minimum_triage: Literal["ROUTINE", "URGENT", "EMERGENCY"] = Field(default="ROUTINE")
    hard_red_flags: list[str] = Field(default_factory=list, description="Life-threatening clinical red flags triggered")
    medication_hard_blocks: list[str] = Field(default_factory=list, description="Hard contraindications triggered")
    mandatory_actions: list[str] = Field(default_factory=list, description="Non-negotiable clinical directives (e.g. Call 115)")
    triggered_rules: list[str] = Field(default_factory=list, description="Safety rule identifiers that triggered")
    disposition: str = Field(default="SAFE")


class ClinicalOutputGuardResult(BaseModel):
    """Output validation result from the independent Clinical Output Guard."""
    safe: bool = Field(description="True if output passes all clinical and medication safety checks")
    violations: list[dict[str, Any]] = Field(default_factory=list, description="Safety violations detected")
    action: Literal["PASS", "REPAIR", "SAFE_FALLBACK"] = Field(default="PASS")
    reasons: list[str] = Field(default_factory=list)

