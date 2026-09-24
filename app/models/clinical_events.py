"""Clinical Event Model schemas for MedGuard AI V6.

Provides structured, evidence-grounded clinical event representations that decouple
medical reasoning from raw linguistic text expressions.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Sequence
from pydantic import BaseModel, ConfigDict, Field


class ClinicalAssertion(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"  # explicitly negated
    UNCERTAIN = "uncertain"


class OnsetTrajectory(str, Enum):
    SUDDEN = "sudden"  # thunderclap, acute within seconds/minutes/hours
    GRADUAL = "gradual"  # insidious onset over days/weeks
    PROGRESSIVE = "progressive"  # worsening over time
    PERSISTENT = "persistent"  # constant unabated symptom
    IMPROVED = "improved"  # partial relief or temporary easing
    EPISODIC = "episodic"  # recurrent paroxysmal bouts


class SeverityLevel(str, Enum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL_EXTREME = "critical_extreme"


class ClinicalEvent(BaseModel):
    """An individual clinical finding or observation grounded in user evidence."""
    model_config = ConfigDict(frozen=True)

    concept: str  # e.g., "vision_loss", "abdominal_rigidity", "arterial_occlusion"
    organ_system: str  # e.g., "ophthalmology", "abdomen", "cardiovascular", "neurology"
    body_site: str | None = None  # e.g., "left_eye", "left_arm", "right_lower_quadrant"
    onset: OnsetTrajectory = OnsetTrajectory.SUDDEN
    severity: SeverityLevel = SeverityLevel.MODERATE
    assertion: ClinicalAssertion = ClinicalAssertion.PRESENT
    temporality: str = "current"  # "current", "historical", "prior_episode"
    experiencer: str = "patient"  # "patient", "family_member", "other"
    physiologic_consequence: str | None = None  # e.g., "limb_perfusion_failure", "peritoneal_irritation"
    functional_loss: str | None = None  # e.g., "loss_of_sight", "loss_of_motor_power"
    certainty: float = Field(default=0.90, ge=0.0, le=1.0)
    evidence_span: str = ""  # exact text span supporting this finding (anti-hallucination ground truth)

    @property
    def is_present(self) -> bool:
        return (
            self.assertion == ClinicalAssertion.PRESENT
            and self.temporality in ("current", "acute", "recent")
            and self.experiencer in ("patient", "patient_consultation")
        )

    @property
    def is_negated(self) -> bool:
        return self.assertion == ClinicalAssertion.ABSENT

    @property
    def is_active_patient_threat(self) -> bool:
        """True if the event is currently active, affirmed, and experienced by the patient."""
        return (
            self.is_present
            and self.temporality in ("current", "acute", "recent")
            and self.experiencer in ("patient", "patient_consultation")
        )

    @property
    def is_critical(self) -> bool:
        return (
            self.severity == SeverityLevel.CRITICAL_EXTREME
            or (self.onset == OnsetTrajectory.SUDDEN and self.severity in (SeverityLevel.SEVERE, SeverityLevel.CRITICAL_EXTREME))
        )


class ClinicalFactSet(BaseModel):
    """The complete set of clinical facts extracted from an interaction."""
    model_config = ConfigDict(frozen=True)

    raw_text: str = ""
    normalized_text: str = ""
    events: tuple[ClinicalEvent, ...] = Field(default_factory=tuple)
    semantic_coverage: float = Field(default=1.0, ge=0.0, le=1.0)
    unrecognized_spans: tuple[str, ...] = Field(default_factory=tuple)

    @property
    def present_events(self) -> list[ClinicalEvent]:
        return [e for e in self.events if e.is_present]

    @property
    def active_patient_events(self) -> list[ClinicalEvent]:
        return [e for e in self.events if e.is_active_patient_threat]

    @property
    def negated_events(self) -> list[ClinicalEvent]:
        return [e for e in self.events if e.is_negated]

    def has_concept(self, concept_name: str | Sequence[str], active_only: bool = True) -> bool:
        targets = {concept_name} if isinstance(concept_name, str) else set(concept_name)
        if active_only:
            return any(e.concept in targets and e.is_active_patient_threat for e in self.events)
        return any(e.concept in targets and e.is_present for e in self.events)

    def has_consequence(self, consequence_name: str | Sequence[str], active_only: bool = True) -> bool:
        targets = {consequence_name} if isinstance(consequence_name, str) else set(consequence_name)
        if active_only:
            return any(e.physiologic_consequence in targets and e.is_active_patient_threat for e in self.events)
        return any(e.physiologic_consequence in targets and e.is_present for e in self.events)

    def has_functional_loss(self, functional_loss_name: str | Sequence[str], onset: OnsetTrajectory | None = None, active_only: bool = True) -> bool:
        targets = {functional_loss_name} if isinstance(functional_loss_name, str) else set(functional_loss_name)
        for e in self.events:
            cond = e.is_active_patient_threat if active_only else e.is_present
            if cond and e.functional_loss in targets:
                if onset is None or e.onset == onset:
                    return True
        return False

    def get_events_for_system(self, organ_system: str, active_only: bool = True) -> list[ClinicalEvent]:
        cond = (lambda e: e.is_active_patient_threat) if active_only else (lambda e: e.is_present)
        return [e for e in self.events if e.organ_system == organ_system and cond(e)]

    def has_critical_consequence(self, active_only: bool = True) -> bool:
        cond = (lambda e: e.is_active_patient_threat) if active_only else (lambda e: e.is_present)
        return any(cond(e) and e.is_critical for e in self.events)
