from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentNarrativeBlock(StrictModel):
    kind: Literal["paragraph", "caution", "urgent"]
    text: str = Field(min_length=1, max_length=2400)
    emphasis: list[str] = Field(default_factory=list, max_length=12)
    claim_ids: list[str] = Field(default_factory=list, max_length=32)
    source_ids: list[str] = Field(default_factory=list, max_length=16)

    @field_validator("source_ids", mode="before")
    @classmethod
    def _normalize_narrative_source_ids(cls, value: Any) -> Any:
        import re
        if isinstance(value, list):
            res = []
            for item in value:
                if isinstance(item, str):
                    item = item.strip()
                    if not item.startswith("src_"):
                        clean = re.sub(r"[^a-zA-Z0-9_-]", "_", item)
                        item = f"src_{clean}"[:40]
                    res.append(item)
                else:
                    res.append(str(item))
            return res
        return value

    @field_validator("claim_ids", mode="before")
    @classmethod
    def _normalize_narrative_claim_ids(cls, value: Any) -> Any:
        import re
        known_prefixes = ("ext_", "title_", "summary_", "action_", "safety_", "finding_", "question_")
        if isinstance(value, list):
            res = []
            for item in value:
                if isinstance(item, str):
                    item = item.strip()
                    if item.startswith("eext_"):
                        item = "ext_" + item[5:]
                    elif item.startswith("e_ext_"):
                        item = "ext_" + item[6:]
                    elif not any(item.startswith(p) for p in known_prefixes):
                        clean = re.sub(r"[^a-zA-Z0-9_-]", "_", item)
                        item = f"ext_{clean}"[:40]
                    res.append(item)
                else:
                    res.append(str(item))
            return res
        return value


class AgentEvidenceSource(StrictModel):
    source_id: str = Field(pattern=r"^src_[a-zA-Z0-9_-]{1,40}$")
    title: str = Field(min_length=1, max_length=300)
    publisher: str = Field(min_length=1, max_length=160)
    url: str = Field(pattern=r"^https://", max_length=1200)
    authority_tier: Literal["guideline_or_regulator", "government_health", "peer_reviewed"]
    supports_claim_ids: list[str] = Field(default_factory=list, max_length=64)

    @field_validator("url", mode="before")
    @classmethod
    def _normalize_url(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return "https://medguard.local/guideline"
            if not value.startswith(("http://", "https://")):
                return f"https://{value}"
            return value
        return value or "https://medguard.local/guideline"

    @field_validator("supports_claim_ids", mode="before")
    @classmethod
    def _normalize_supports_claim_ids(cls, value: Any) -> Any:
        import re
        known_prefixes = ("ext_", "title_", "summary_", "action_", "safety_", "finding_", "question_")
        if isinstance(value, list):
            res = []
            for item in value:
                if isinstance(item, str):
                    item = item.strip()
                    if item.startswith("eext_"):
                        item = "ext_" + item[5:]
                    elif item.startswith("e_ext_"):
                        item = "ext_" + item[6:]
                    elif not any(item.startswith(p) for p in known_prefixes):
                        clean = re.sub(r"[^a-zA-Z0-9_-]", "_", item)
                        item = f"ext_{clean}"[:40]
                    res.append(item)
                else:
                    res.append(str(item))
            return res
        return value

    @field_validator("source_id", mode="before")
    @classmethod
    def _normalize_source_id(cls, value: Any) -> Any:
        import re
        if isinstance(value, str):
            value = value.strip()
            if not value.startswith("src_"):
                clean = re.sub(r"[^a-zA-Z0-9_-]", "_", value)
                return f"src_{clean}"[:40]
        return value

    @field_validator("authority_tier", mode="before")
    @classmethod
    def _normalize_authority(cls, value: Any) -> Any:
        valid = {"guideline_or_regulator", "government_health", "peer_reviewed"}
        if value not in valid:
            return "guideline_or_regulator"
        return value


class AgentEvidenceClaim(StrictModel):
    claim_id: str = Field(pattern=r"^ext_[a-zA-Z0-9_-]{1,40}$")
    text: str = Field(min_length=1, max_length=1200)
    source_ids: list[str] = Field(default_factory=list, max_length=16)

    @field_validator("source_ids", mode="before")
    @classmethod
    def _normalize_claim_source_ids(cls, value: Any) -> Any:
        import re
        if isinstance(value, list):
            res = []
            for item in value:
                if isinstance(item, str):
                    item = item.strip()
                    if not item.startswith("src_"):
                        clean = re.sub(r"[^a-zA-Z0-9_-]", "_", item)
                        item = f"src_{clean}"[:40]
                    res.append(item)
                else:
                    res.append(str(item))
            return res
        return value

    @field_validator("claim_id", mode="before")
    @classmethod
    def _normalize_claim_id(cls, value: Any) -> Any:
        import re
        if isinstance(value, str):
            value = value.strip()
            if not value.startswith("ext_"):
                clean = re.sub(r"[^a-zA-Z0-9_-]", "_", value)
                return f"ext_{clean}"[:40]
        return value


class AgentQuestionAnalysis(StrictModel):
    interpreted_request: str = Field(min_length=1, max_length=600)
    key_questions: list[str] = Field(default_factory=list, max_length=12)
    ambiguities: list[str] = Field(default_factory=list, max_length=12)
    risk_level: Literal["low", "medium", "high"]


class AgentDraft(StrictModel):
    question_analysis: AgentQuestionAnalysis
    evidence_claims: list[AgentEvidenceClaim] = Field(default_factory=list, max_length=24)
    narrative: list[AgentNarrativeBlock] = Field(min_length=1, max_length=8)
    sources: list[AgentEvidenceSource] = Field(default_factory=list, max_length=16)
    notes: str = Field(default="", max_length=1500)


class VerificationScores(StrictModel):
    grounding: float = Field(ge=0, le=1)
    safety: float = Field(ge=0, le=1)
    completeness: float = Field(ge=0, le=1)
    clarity: float = Field(ge=0, le=1)
    citation_coverage: float = Field(ge=0, le=1)

    @field_validator("grounding", "safety", "completeness", "clarity", "citation_coverage", mode="before")
    @classmethod
    def _clamp_score(cls, value: Any) -> float:
        try:
            val = float(value)
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 0.0


class AgentVerification(StrictModel):
    approved: bool
    scores: VerificationScores
    issues: list[str] = Field(default_factory=list, max_length=24, exclude=True)
    missing_claim_ids: list[str] = Field(default_factory=list, max_length=64, exclude=True)
    unsupported_claims: list[str] = Field(default_factory=list, max_length=24, exclude=True)
    source_issues: list[str] = Field(default_factory=list, max_length=24, exclude=True)
    summary: str = Field(default="Verification completed", min_length=1, max_length=800, exclude=True)


class ShadowWriterAssessment(StrictModel):
    """Compact NLP quality assessment used by a local background model.

    Shadow mode never rewrites the patient-facing answer.  Keeping this
    contract small lets a resource-constrained Ollama model assess language
    quality without generating the much larger evidence-authoring schema.
    """

    triage_consistent: bool
    action_priority_clear: bool
    uncertainty_calibrated: bool
    professional_tone: bool
    communication_class: Literal[
        "supportive_safe",
        "alarming_but_appropriate",
        "neutral",
        "falsely_reassuring",
        "panic_inducing",
    ]
    critical_issues: list[str] = Field(default_factory=list, max_length=5)
    concise_summary: str = Field(min_length=1, max_length=400)


class ShadowVerifierAssessment(StrictModel):
    """Independent compact check of the writer's shadow assessment."""

    approved: bool
    safety_score: float = Field(ge=0, le=1)
    clarity_score: float = Field(ge=0, le=1)
    consistency_score: float = Field(ge=0, le=1)
    issues: list[str] = Field(default_factory=list, max_length=5)
    summary: str = Field(min_length=1, max_length=400)

    @field_validator("safety_score", "clarity_score", "consistency_score", mode="before")
    @classmethod
    def _normalize_local_score(cls, value: Any) -> float:
        """Accept the common 0-10 local-model scale and normalize to 0-1."""
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        if 1 < score <= 10:
            score /= 10
        return max(0.0, min(1.0, score))


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
    domain: Literal["clinical", "pharmacology"] | None = Field(default=None, exclude=True)
