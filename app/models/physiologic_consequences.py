"""Physiologic Consequence Models for MedGuard AI (V7 Architecture).

Represents abstract, standardized pathophysiologic failure patterns rather than
named disease diagnoses. Decouples clinical urgency from disease naming.

Standardized Consequence Dimensions:
1. airway_obstruction: Upper or lower airway patency failure.
2. respiratory_failure: Acute alveolar/ventilatory compromise or severe tachypnea.
3. circulatory_compromise: Systemic hypoperfusion, shock, hypotension, or mottling.
4. organ_hypoperfusion: Target organ ischemia (mesenteric, renal, cerebral).
5. acute_tissue_ischemia: Severe tissue/limb arterial compromise or compartment syndrome.
6. internal_hemorrhage: Concealed major blood loss, hemoperitoneum, or vascular rupture.
7. perforation_risk: Visceral hollow-organ transmural rupture (esophageal, gastric, intestinal).
8. systemic_toxic_state: Severe sepsis, septic shock, toxidrome (NMS, serotonin syndrome, severe poisoning).
9. acute_neurologic_functional_loss: Focal motor/sensory/cranial deficits, acute herniation risk.
10. major_barrier_failure: Necrotizing deep soft-tissue destruction, crepitus, hemorrhagic bullae.
11. metabolic_instability: Severe ketoacidosis, profound hypoglycemia, lethal electrolyte derangement.
12. time_critical_organ_loss: Irreversible organ infarction window (torsion, arterial occlusion, septic joint).
"""

from __future__ import annotations

from enum import Enum
from typing import Sequence
from pydantic import BaseModel, ConfigDict, Field


class PhysiologicConsequenceType(str, Enum):
    AIRWAY_OBSTRUCTION = "airway_obstruction"
    RESPIRATORY_FAILURE = "respiratory_failure"
    CIRCULATORY_COMPROMISE = "circulatory_compromise"
    ORGAN_HYPOPERFUSION = "organ_hypoperfusion"
    ACUTE_TISSUE_ISCHEMIA = "acute_tissue_ischemia"
    INTERNAL_HEMORRHAGE = "internal_hemorrhage"
    PERFORATION_RISK = "perforation_risk"
    SYSTEMIC_TOXIC_STATE = "systemic_toxic_state"
    ACUTE_NEUROLOGIC_FUNCTIONAL_LOSS = "acute_neurologic_functional_loss"
    MAJOR_BARRIER_FAILURE = "major_barrier_failure"
    METABOLIC_INSTABILITY = "metabolic_instability"
    TIME_CRITICAL_ORGAN_LOSS = "time_critical_organ_loss"


class ConsequenceSeverity(str, Enum):
    IMMINENT_LETHAL = "IMMINENT_LETHAL"       # T4 pure emergency (death within minutes/hours)
    SEVERE_PROGRESSIVE = "SEVERE_PROGRESSIVE" # T4/T3 acute organ loss or rapid deterioration
    MODERATE = "MODERATE"                     # T3 urgent evaluation required
    MILD_OR_NONE = "MILD_OR_NONE"             # Routine/stable


class PhysiologicConsequence(BaseModel):
    """An instantiated pathophysiologic consequence deduced from clinical facts."""
    model_config = ConfigDict(frozen=True)

    consequence_type: PhysiologicConsequenceType
    severity: ConsequenceSeverity = ConsequenceSeverity.SEVERE_PROGRESSIVE
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    supporting_findings: tuple[str, ...] = Field(default_factory=tuple)
    pathophysiologic_rationale: str = ""
    time_window_hours: float | None = None

    @property
    def is_emergency(self) -> bool:
        return self.severity in (ConsequenceSeverity.IMMINENT_LETHAL, ConsequenceSeverity.SEVERE_PROGRESSIVE)


class PhysiologicAssessment(BaseModel):
    """The aggregate assessment across all 12 pathophysiologic dimensions."""
    model_config = ConfigDict(frozen=True)

    active_consequences: tuple[PhysiologicConsequence, ...] = Field(default_factory=tuple)
    primary_threat_summary: str = "Không ghi nhận rối loạn sinh lý bệnh học cấp tính nguy hiểm."
    max_severity: ConsequenceSeverity = ConsequenceSeverity.MILD_OR_NONE

    @property
    def has_emergency_consequence(self) -> bool:
        return any(c.is_emergency for c in self.active_consequences)

    @property
    def emergency_consequences(self) -> list[PhysiologicConsequence]:
        return [c for c in self.active_consequences if c.is_emergency]
