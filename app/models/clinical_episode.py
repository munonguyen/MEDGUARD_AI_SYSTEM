from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DecisionImpact = Literal["low", "medium", "high", "critical"]
FactPolarity = Literal["present", "absent"]


class EpisodeFact(BaseModel):
    """One user-grounded fact in the active clinical episode.

    ``absent`` is reserved for an explicitly negated finding. A finding that the
    user simply did not mention must never be represented here as absent.
    """

    model_config = ConfigDict(frozen=True)

    concept: str
    polarity: FactPolarity
    organ_system: str | None = None
    body_site: str | None = None
    onset: str | None = None
    severity: str | None = None
    evidence_span: str
    source_turn: int = Field(ge=1)
    temporality: str = "current"


class DecisionUnknown(BaseModel):
    """Decision-relevant information that is genuinely unknown, not negative."""

    model_config = ConfigDict(frozen=True)

    key: str
    question: str
    impact: DecisionImpact
    changes: tuple[str, ...] = Field(default_factory=tuple)
    rationale: str


class EpisodeDelta(BaseModel):
    """Facts introduced by the latest user turn relative to prior episode state."""

    model_config = ConfigDict(frozen=True)

    new_positive: tuple[str, ...] = Field(default_factory=tuple)
    new_negative: tuple[str, ...] = Field(default_factory=tuple)
    new_historical_risk: tuple[str, ...] = Field(default_factory=tuple)
    episode_switched: bool = False


class ClinicalEpisodeModel(BaseModel):
    """Writer-facing, diagnosis-neutral model of the current clinical story."""

    model_config = ConfigDict(frozen=True)

    version: str = "v25.1"
    episode_id: str
    chief_domain: str | None = None
    latest_user_message: str
    problem_representation: str
    confirmed_positive: tuple[EpisodeFact, ...] = Field(default_factory=tuple)
    confirmed_negative: tuple[EpisodeFact, ...] = Field(default_factory=tuple)
    unknown_decision_relevant: tuple[DecisionUnknown, ...] = Field(default_factory=tuple)
    historical_risk: tuple[EpisodeFact, ...] = Field(default_factory=tuple)
    delta: EpisodeDelta
    semantic_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    user_turns_in_active_episode: int = Field(default=1, ge=1)
    has_hard_historical_risk: bool = False

    def to_agent_payload(self) -> dict:
        return self.model_dump(mode="json")
