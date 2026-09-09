from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentNarrativeBlock(StrictModel):
    kind: Literal["paragraph", "caution", "urgent"]
    text: str = Field(min_length=1, max_length=2400)
    emphasis: list[str] = Field(max_length=12)
    claim_ids: list[str] = Field(min_length=1, max_length=32)
    source_ids: list[str] = Field(min_length=1, max_length=16)


class AgentEvidenceSource(StrictModel):
    source_id: str = Field(pattern=r"^src_[a-zA-Z0-9_-]{1,40}$")
    title: str = Field(min_length=1, max_length=300)
    publisher: str = Field(min_length=1, max_length=160)
    url: str = Field(pattern=r"^https://", max_length=1200)
    authority_tier: Literal["guideline_or_regulator", "government_health", "peer_reviewed"]
    supports_claim_ids: list[str] = Field(min_length=1, max_length=64)


class AgentEvidenceClaim(StrictModel):
    claim_id: str = Field(pattern=r"^ext_[a-zA-Z0-9_-]{1,40}$")
    text: str = Field(min_length=1, max_length=1200)
    source_ids: list[str] = Field(min_length=1, max_length=16)


class AgentQuestionAnalysis(StrictModel):
    interpreted_request: str = Field(min_length=1, max_length=600)
    key_questions: list[str] = Field(min_length=1, max_length=12)
    ambiguities: list[str] = Field(max_length=12)
    risk_level: Literal["low", "medium", "high"]


class AgentDraft(StrictModel):
    question_analysis: AgentQuestionAnalysis
    evidence_claims: list[AgentEvidenceClaim] = Field(max_length=24)
    narrative: list[AgentNarrativeBlock] = Field(min_length=1, max_length=8)
    sources: list[AgentEvidenceSource] = Field(min_length=1, max_length=16)
    notes: str = Field(max_length=500)


class VerificationScores(StrictModel):
    grounding: float = Field(ge=0, le=1)
    safety: float = Field(ge=0, le=1)
    completeness: float = Field(ge=0, le=1)
    clarity: float = Field(ge=0, le=1)
    citation_coverage: float = Field(ge=0, le=1)


class AgentVerification(StrictModel):
    approved: bool
    scores: VerificationScores
    issues: list[str] = Field(max_length=24, exclude=True)
    missing_claim_ids: list[str] = Field(max_length=64, exclude=True)
    unsupported_claims: list[str] = Field(max_length=24, exclude=True)
    source_issues: list[str] = Field(max_length=24, exclude=True)
    summary: str = Field(min_length=1, max_length=800, exclude=True)


class AgentStageTrace(BaseModel):
    role: Literal["answer", "verifier"]
    provider: str
    model: str
    status: Literal["not_run", "success", "error", "circuit_open"]
    response_id: str | None = None
    latency_ms: int = 0
    estimated_input_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cache_hit: bool = False


class AnswerAgentTrace(BaseModel):
    mode: Literal["disabled", "shadow", "enforced"] = Field(exclude=True)
    status: Literal["disabled", "unavailable", "verified", "shadow", "rejected", "error", "circuit_open"]
    generator: AgentStageTrace | None = Field(default=None, exclude=True)
    verifier: AgentStageTrace | None = Field(default=None, exclude=True)
    verification: AgentVerification | None = None
    question_analysis: AgentQuestionAnalysis | None = Field(default=None, exclude=True)
    search_queries: list[str] = Field(default_factory=list, exclude=True)
    verifier_citation_urls: list[str] = Field(default_factory=list, exclude=True)
    fallback_reason: str | None = Field(default=None, exclude=True)
    risk_class: str | None = Field(default=None, exclude=True)
    cache_policy: str | None = Field(default=None, exclude=True)
