from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.common import DisclaimerMixin, Trace


class QueueItem(BaseModel):
    patient_ref: str = Field(min_length=1, max_length=128)
    urgency: Literal["EMERGENCY", "URGENT", "ROUTINE"]
    esi_level: int | None = Field(default=None, ge=1, le=5)
    emergency_flag: bool = False
    arrived_at: datetime | None = None
    wait_minutes: int = Field(default=0, ge=0)
    specialty_code: str | None = None

    @field_validator("patient_ref")
    @classmethod
    def patient_ref_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("patient_ref must not be blank")
        return value


class QueuePrioritizeRequest(BaseModel):
    items: list[QueueItem] = Field(min_length=1, max_length=500)
    locale: str = "vi-VN"


class PrioritizedQueueItem(BaseModel):
    patient_ref: str
    rank: int
    priority_score: float
    priority_band: Literal["EMERGENCY", "URGENT", "ROUTINE"]
    rationale: list[str] = Field(default_factory=list)


class QueuePrioritizeResponse(DisclaimerMixin):
    request_id: str
    status: Literal["ok"] = "ok"
    items: list[PrioritizedQueueItem]
    trace: Trace
