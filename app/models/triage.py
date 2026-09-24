from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.common import DisclaimerMixin, Status, Trace


class CurrentMedication(BaseModel):
    name: str
    active_ingredient: str | None = None
    dose_mg: float | None = None


class VitalSigns(BaseModel):
    systolic: int | None = None
    diastolic: int | None = None
    heart_rate: int | None = None
    temperature_c: float | None = None
    spo2: int | None = None


class TriageRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    patient_ref: str = Field(min_length=1, max_length=128)
    symptoms_text: str = Field(min_length=1)
    age: int | None = None
    sex: Literal["male", "female", "other"] | None = None
    known_conditions: list[str] = Field(default_factory=list)
    current_medications: list[CurrentMedication] = Field(default_factory=list)
    vitals: VitalSigns | None = Field(default=None, alias="vital_signs")
    locale: str = "vi-VN"

    @field_validator("patient_ref")
    @classmethod
    def patient_ref_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("patient_ref must not be blank")
        return value


class RecommendedSpecialty(BaseModel):
    code: str
    label: str
    confidence: float


class TriageResponse(DisclaimerMixin):
    request_id: str
    status: Status = Status.ok
    urgency: Literal["EMERGENCY", "URGENT", "ROUTINE"]
    emergency_flag: bool
    esi_level: int | None = None
    recommended_specialty: RecommendedSpecialty | None = None
    red_flags: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    self_care: list[str] = Field(default_factory=list)
    safety_net: list[str] = Field(default_factory=list)
    guidance_summary: str | None = None
    clinical_hypotheses: list[str] = Field(default_factory=list)
    advice: str
    trace: Trace
