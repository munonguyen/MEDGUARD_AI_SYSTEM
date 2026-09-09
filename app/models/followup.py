from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.common import DisclaimerMixin, Status, Trace


class FollowUpRequest(BaseModel):
    patient_ref: str = Field(min_length=1, max_length=128)
    diagnosis_text: str = Field(min_length=1)
    discharge_date: date | None = None
    current_medications: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    customer_rules: dict[str, int] = Field(default_factory=dict)
    locale: str = "vi-VN"

    @field_validator("patient_ref")
    @classmethod
    def patient_ref_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("patient_ref must not be blank")
        return value

    @field_validator("customer_rules")
    @classmethod
    def customer_rules_must_be_non_negative(cls, value: dict[str, int]) -> dict[str, int]:
        if any(days < 0 for days in value.values()):
            raise ValueError("customer rule due_in_days must be non-negative")
        return value


class FollowUpSuggestion(BaseModel):
    code: str
    title: str
    due_in_days: int
    scheduled_for: date | None = None
    instructions: list[str] = Field(default_factory=list)
    basis: Literal["rule", "customer_rule"]
    confidence: float


class FollowUpPlanResponse(DisclaimerMixin):
    request_id: str
    status: Status = Status.ok
    plan_available: bool
    suggestions: list[FollowUpSuggestion] = Field(default_factory=list)
    summary: str
    trace: Trace
