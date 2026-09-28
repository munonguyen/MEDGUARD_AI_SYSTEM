from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SeverityChoice(str, Enum):
    ROUTINE = "ROUTINE"
    URGENT = "URGENT"
    EMERGENCY = "EMERGENCY"
    UNKNOWN = "UNKNOWN"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class SeverityAgent(str, Enum):
    ROUTINE = "routine"
    URGENT = "urgent"
    EMERGENCY = "emergency"
    UNCERTAIN = "uncertain"
    NON_CLINICAL = "non_clinical"


class ModelTier(str, Enum):
    FAST = "fast"
    STANDARD = "standard"
    DEEP = "deep"


class KevDecisionSignal(BaseModel):
    """Advisory System-One routing signal.

    ``severity_score`` is an ordinal routing score, not a probability of
    serious illness. Kev never owns the clinical disposition; it only informs
    dispatch difficulty/uncertainty after the deterministic safety floor and
    structured clinical reasoner have produced their result.
    """

    choice: SeverityChoice
    probabilities: dict[str, float] = Field(default_factory=dict)
    severity_score: float | None = Field(default=None, ge=0.0, le=4.0)
    choice_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    score_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    entropy: float | None = Field(default=None, ge=0.0)
    source: Literal["kev", "clinical_fallback", "test"] = "kev"

    @model_validator(mode="after")
    def normalize_probabilities(self) -> "KevDecisionSignal":
        if not self.probabilities:
            return self
        cleaned = {str(key).upper(): max(0.0, float(value)) for key, value in self.probabilities.items()}
        total = sum(cleaned.values())
        if total > 0:
            self.probabilities = {key: value / total for key, value in cleaned.items()}
        return self

    @property
    def margin(self) -> float:
        values = sorted(self.probabilities.values(), reverse=True)
        if len(values) < 2:
            return self.choice_confidence
        return max(0.0, values[0] - values[1])


class AdaptiveRouteDecision(BaseModel):
    """Single-path dispatch decision that cannot rewrite clinical truth."""

    clinical_task: str
    resolved_severity: Literal["ROUTINE", "URGENT", "EMERGENCY"] | None = None
    agent: SeverityAgent
    model_tier: ModelTier
    emergency_lock: bool = False
    requires_clarification: bool = False
    requires_review: bool = False
    kev_choice: SeverityChoice
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    margin: float = Field(default=0.0, ge=0.0, le=1.0)
    fact_coverage: float = Field(default=1.0, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
