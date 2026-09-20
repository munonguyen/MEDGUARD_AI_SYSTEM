"""Semantic Clinical Abstraction Models for MedGuard AI (V8 Architecture).

Provides intermediate abstractions between natural language surface expressions
and structured ClinicalEvent / ClinicalThreatGraph models:
- FunctionalLossAbstraction: loss of perfusion, vision, motor power, speech, airway, barrier.
- PhysiologicThreatAbstraction: subcutaneous emphysema, post-vomiting chest pain, peritonism, shock.
- ToxicExposureAbstraction: substance exposure, autonomic flux, neuromuscular rigidity, toxidrome cues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence
from pydantic import BaseModel, ConfigDict, Field


class AbstractionCategory(str, Enum):
    FUNCTIONAL_LOSS = "functional_loss"
    PHYSIOLOGIC_INSTABILITY = "physiologic_instability"
    SURGICAL_BARRIER_FAILURE = "surgical_barrier_failure"
    TOXIC_METABOLIC_EXPOSURE = "toxic_metabolic_exposure"
    BENIGN_COMPLAINT = "benign_complaint"


class ClinicalAbstraction(BaseModel):
    """An abstract clinical concept derived from surface language expressions."""
    model_config = ConfigDict(frozen=True)

    abstraction_id: str  # e.g., "loss_of_limb_perfusion", "subcutaneous_crepitus"
    category: AbstractionCategory
    acuity_weight: float = Field(default=0.90, ge=0.0, le=1.0)
    is_critical_threat: bool = False
    evidence_span: str = ""
    associated_functional_loss: str | None = None
    associated_physiologic_consequence: str | None = None
    canonical_concept: str = ""
    rationale: str = ""


class SemanticAbstractionResult(BaseModel):
    """Collection of clinical abstractions synthesized from patient discourse."""
    model_config = ConfigDict(frozen=True)

    abstractions: tuple[ClinicalAbstraction, ...] = Field(default_factory=tuple)
    has_critical_functional_loss: bool = False
    has_physiologic_instability: bool = False
    has_toxic_exposure_threat: bool = False
    has_surgical_barrier_threat: bool = False
    is_unambiguously_benign: bool = False
    abstraction_summary: str = ""

    def has_abstraction(self, abstraction_ids: str | Sequence[str]) -> bool:
        if isinstance(abstraction_ids, str):
            ids = {abstraction_ids}
        else:
            ids = set(abstraction_ids)
        return any(a.abstraction_id in ids for a in self.abstractions)

    @property
    def critical_abstractions(self) -> list[ClinicalAbstraction]:
        return [a for a in self.abstractions if a.is_critical_threat]
