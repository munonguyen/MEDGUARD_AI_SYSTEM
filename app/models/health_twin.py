from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


OrganId = Literal[
    "head",
    "ent",
    "cardiovascular",
    "lungs",
    "stomach",
    "liver",
    "kidneys",
    "spine_joints",
    "skin",
]

OrganStatusType = Literal[
    "normal",
    "monitoring",
    "inflamed",
    "critical",
    "adverse_reaction",
]

TimelinePhase = Literal[
    "initial_onset",
    "under_treatment",
    "improved_recovering",
    "adverse_event_escalation",
    "fully_resolved",
    "baseline",
]


class OrganCoordinates(BaseModel):
    x: float = Field(description="Percentage X coordinate on SVG body (0-100)")
    y: float = Field(description="Percentage Y coordinate on SVG body (0-100)")


class FutureRiskPrognosis(BaseModel):
    risk_level: Literal["low", "moderate", "high", "critical"] = "low"
    risk_title: str
    latent_risk_description: str
    timeframe: str = "3 - 5 năm"
    vaccination_status: str | None = None
    potential_progression: str = ""
    preventive_recommendations: list[str] = Field(default_factory=list)
    screening_tests: list[str] = Field(default_factory=list)


class OrganStatus(BaseModel):
    id: OrganId
    name: str
    vietnamese_name: str
    status: OrganStatusType = "normal"
    health_score: int = Field(default=100, ge=0, le=100)
    pain_level: int = Field(default=0, ge=0, le=10)
    inflammation_level: Literal["none", "mild", "moderate", "severe"] = "none"
    symptoms: list[str] = Field(default_factory=list)
    clinical_notes: str = ""
    related_medications: list[str] = Field(default_factory=list)
    warning: str | None = None
    is_adverse_reaction: bool = False
    contraindicated_actions: list[str] = Field(default_factory=list)
    coordinates: OrganCoordinates
    future_risk: FutureRiskPrognosis | None = None


class VitalSignsSummary(BaseModel):
    heart_rate_bpm: int = 76
    blood_pressure_systolic: int = 120
    blood_pressure_diastolic: int = 80
    temperature_celsius: float = 37.0
    spo2_percent: int = 98
    overall_pain_level: int = 0


class RecoveryTimelinePoint(BaseModel):
    id: str
    timestamp: str
    phase: TimelinePhase
    title: str
    trigger_message: str
    health_score: int
    status_label: str
    clinical_summary: str
    ai_directive: str
    medications_adjusted: list[str] = Field(default_factory=list)


class SafeGuardrailAlert(BaseModel):
    alert_level: Literal["warning", "danger", "critical"]
    title: str
    cause_identified: str
    contraindicated_item: str
    required_action: str
    alternative_recommendation: str
    seek_emergency: bool = False


class PatientHealthProfile(BaseModel):
    patient_id: str = "demo-patient-001"
    patient_name: str = "Bệnh nhân MedGuard"
    age: int = 34
    gender: str = "Nam"
    active_diagnosis: str = "Theo dõi cảm cúm & tiến triển lâm sàng"
    overall_health_score: int = Field(default=82, ge=0, le=100)
    health_trend: Literal["improving", "deteriorating", "stable", "critical_alert"] = "stable"
    vitals: VitalSignsSummary = Field(default_factory=VitalSignsSummary)
    organs: list[OrganStatus] = Field(default_factory=list)
    active_medications: list[str] = Field(default_factory=list)
    discontinued_medications: list[str] = Field(default_factory=list)
    contraindicated_regimens: list[str] = Field(default_factory=list)
    clinical_directives: list[str] = Field(default_factory=list)
    safe_guardrail_alert: SafeGuardrailAlert | None = None
    timeline: list[RecoveryTimelinePoint] = Field(default_factory=list)
    overall_future_risks: list[FutureRiskPrognosis] = Field(default_factory=list)
    last_updated: str = Field(default_factory=lambda: datetime.now().strftime("%H:%M %d/%m/%Y"))


class EvaluateProgressRequest(BaseModel):
    patient_id: str | None = "demo-patient-001"
    message: str = Field(min_length=1, max_length=2000)
    current_medications: list[str] | None = None
    vital_updates: dict[str, Any] | None = None


class EvaluateProgressResponse(BaseModel):
    status: str = "success"
    detected_event: Literal[
        "recovery",
        "deterioration",
        "adverse_reaction",
        "new_symptom",
        "initial_onset",
        "symptom_update",
        "vaccine_risk_alert",
        "vaccine_verified",
        "inquiry",
    ]
    ai_analysis: str
    action_plan: str
    must_discontinue_previous: bool = False
    discontinued_items: list[str] = Field(default_factory=list)
    profile: PatientHealthProfile


class ScenarioSwitchRequest(BaseModel):
    scenario_id: Literal["initial_flu", "recovered_headache", "adr_stomach_nsaid", "severe_fever_progression", "healthy_baseline"]
