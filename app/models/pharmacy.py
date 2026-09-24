from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.common import DisclaimerMixin, Status, Trace


class FulfillmentMedication(BaseModel):
    name: str
    active_ingredient: str | None = None
    dose_mg: float | None = None
    quantity: int | None = Field(default=None, ge=1)


class FulfillmentRequest(BaseModel):
    patient_ref: str = Field(min_length=1, max_length=128)
    medications: list[FulfillmentMedication] = Field(min_length=1)
    location_hint: str | None = None
    preferred_mode: Literal["pickup", "delivery"] = "pickup"
    urgency: Literal["EMERGENCY", "URGENT", "ROUTINE"] = "ROUTINE"
    locale: str = "vi-VN"

    @field_validator("patient_ref")
    @classmethod
    def patient_ref_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("patient_ref must not be blank")
        return value


class PharmacyOption(BaseModel):
    provider_code: str
    provider_name: str
    mode: Literal["pickup", "delivery"]
    availability: Literal["AVAILABLE", "LIMITED", "UNAVAILABLE"]
    eta_minutes: int | None = None
    distance_km: float | None = None
    confidence: float
    rationale: list[str] = Field(default_factory=list)


class PharmacyFulfillmentResponse(DisclaimerMixin):
    request_id: str
    status: Status = Status.ok
    needs_human_review: bool
    recommended_mode: Literal["pickup", "delivery"]
    options: list[PharmacyOption] = Field(default_factory=list)
    summary: str
    trace: Trace
