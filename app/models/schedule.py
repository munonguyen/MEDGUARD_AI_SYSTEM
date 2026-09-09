from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class MedicationScheduleCreate(BaseModel):
    patient_ref: str = Field(min_length=1, max_length=128)
    medication_name: str = Field(min_length=1, max_length=255)
    dosage_text: str | None = Field(default=None, max_length=255)
    scheduled_at: datetime
    recurrence: Literal["once", "daily"] = "once"
    source: Literal["chat", "prescription_review"] = "chat"

    @field_validator("patient_ref", "medication_name")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


class MedicationSchedule(BaseModel):
    schedule_id: str
    tenant_id: str
    patient_ref: str
    medication_name: str
    dosage_text: str | None = None
    scheduled_at: datetime
    recurrence: Literal["once", "daily"]
    source: Literal["chat", "prescription_review"]
    status: Literal["active", "cancelled"] = "active"
    created_at: datetime


class MedicationScheduleList(BaseModel):
    schedules: list[MedicationSchedule] = Field(default_factory=list)
