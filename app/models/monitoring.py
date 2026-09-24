from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.common import DisclaimerMixin, Status, Trace


class MonitoringPoint(BaseModel):
    metric: Literal[
        "pain_score",
        "temperature_c",
        "systolic",
        "diastolic",
        "heart_rate",
        "spo2",
        "glucose_mg_dl",
    ]
    value: float
    unit: str
    recorded_at: datetime

    @model_validator(mode="after")
    def validate_metric_value_and_unit(self) -> "MonitoringPoint":
        constraints = {
            "pain_score": (0.0, 10.0, {"score", "/10"}),
            "temperature_c": (25.0, 45.0, {"c", "celsius", "°c"}),
            "systolic": (40.0, 300.0, {"mmhg"}),
            "diastolic": (20.0, 200.0, {"mmhg"}),
            "heart_rate": (20.0, 300.0, {"bpm", "beats/min"}),
            "spo2": (0.0, 100.0, {"%", "percent"}),
            "glucose_mg_dl": (0.0, 1500.0, {"mg/dl", "mg_dl"}),
        }
        minimum, maximum, units = constraints[self.metric]
        if not minimum <= self.value <= maximum:
            raise ValueError(f"{self.metric} must be between {minimum:g} and {maximum:g}")
        if self.unit.strip().lower() not in units:
            expected = ", ".join(sorted(units))
            raise ValueError(f"{self.metric} unit must be one of: {expected}")
        return self


class MonitoringRequest(BaseModel):
    patient_ref: str = Field(min_length=1, max_length=128)
    plan_ref: str | None = None
    metrics: list[MonitoringPoint] = Field(min_length=1)
    locale: str = "vi-VN"

    @field_validator("patient_ref")
    @classmethod
    def patient_ref_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("patient_ref must not be blank")
        return value


class MonitoringTrend(BaseModel):
    metric: str
    direction: Literal["up", "down", "stable", "unknown"]
    delta: float | None = None


class MonitoringAlert(BaseModel):
    metric: str
    severity: Literal["LOW", "MODERATE", "HIGH"]
    detail: str
    basis: Literal["threshold", "trend", "insufficient_data"]
    confidence: float


class MonitoringResponse(DisclaimerMixin):
    request_id: str
    status: Status = Status.ok
    trend: Literal["insufficient_data", "stable", "improving", "worsening"]
    escalation_level: Literal["NONE", "SELF_CARE", "CLINIC", "URGENT", "EMERGENCY"]
    alerts: list[MonitoringAlert] = Field(default_factory=list)
    metrics: list[MonitoringTrend] = Field(default_factory=list)
    summary: str
    trace: Trace
