"""Strict contracts for independently reviewed Answer and Verifier datasets."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExpertReview(StrictModel):
    status: Literal["approved", "rejected", "pending"]
    reviewer_role: Literal[
        "physician",
        "pharmacist",
        "clinical_safety",
        "data_governance",
    ]
    review_id: str = Field(pattern=r"^review-[a-zA-Z0-9._-]{4,80}$")
    reviewed_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T")


class DataProvenance(StrictModel):
    source_id: str = Field(pattern=r"^[a-zA-Z0-9._/-]{3,160}$")
    source_kind: Literal[
        "licensed_internal",
        "public_authoritative",
        "synthetic_adversarial",
        "external_evaluation",
    ]
    license_id: str = Field(min_length=2, max_length=160)
    usage_rights_confirmed: bool
    dataset_version: str = Field(min_length=1, max_length=80)


class EvidenceItem(StrictModel):
    evidence_id: str = Field(pattern=r"^evidence-[a-zA-Z0-9._-]{1,80}$")
    source_uri: str = Field(min_length=1, max_length=1200)
    source_version: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=4000)


class AnswerTarget(StrictModel):
    narrative: list[str] = Field(min_length=1, max_length=12)
    questions: list[str] = Field(default_factory=list, max_length=12)
    cited_evidence_ids: list[str] = Field(default_factory=list, max_length=32)
    abstains_from_diagnosis: bool
    escalation_required: bool


class AnswerTrainingSample(StrictModel):
    schema_version: Literal["medguard.answer.v1"]
    role: Literal["answer"]
    sample_id: str = Field(pattern=r"^answer-[a-zA-Z0-9._-]{4,100}$")
    case_group_id: str = Field(pattern=r"^case-[a-zA-Z0-9._-]{4,100}$")
    task_category: Literal[
        "clinical_qa",
        "triage_explanation",
        "drug_safety",
        "refusal_uncertainty",
        "tool_grounded_qa",
        "adversarial_safety",
    ]
    locale: str = Field(pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")
    deidentified: bool
    provenance: DataProvenance
    expert_review: ExpertReview
    question: str = Field(min_length=1, max_length=4000)
    patient_context: dict[str, Any] = Field(default_factory=dict)
    tool_results: dict[str, Any] = Field(default_factory=dict)
    knowledge_evidence: list[EvidenceItem] = Field(default_factory=list, max_length=32)
    locked_claims: list[str] = Field(default_factory=list, max_length=32)
    target: AnswerTarget

    @model_validator(mode="after")
    def target_must_preserve_locked_claims(self) -> "AnswerTrainingSample":
        narrative = "\n".join(self.target.narrative)
        missing = [claim for claim in self.locked_claims if claim not in narrative]
        if missing:
            raise ValueError("target narrative does not preserve every locked claim")
        known_evidence = {item.evidence_id for item in self.knowledge_evidence}
        if set(self.target.cited_evidence_ids) - known_evidence:
            raise ValueError("target cites evidence not supplied by the sample")
        return self


class VerifierTarget(StrictModel):
    approved: bool
    violation_types: list[
        Literal[
            "unsupported_claim",
            "missing_safety_warning",
            "wrong_medication",
            "changed_triage_level",
            "invalid_citation",
            "unsafe_instruction",
            "none",
        ]
    ] = Field(min_length=1, max_length=16)
    required_missing_claim_ids: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def verdict_matches_violations(self) -> "VerifierTarget":
        if self.approved and self.violation_types != ["none"]:
            raise ValueError("approved verifier samples must use only the none violation")
        if not self.approved and "none" in self.violation_types:
            raise ValueError("rejected verifier samples must contain a concrete violation")
        return self


class VerifierTrainingSample(StrictModel):
    schema_version: Literal["medguard.verifier.v1"]
    role: Literal["verifier"]
    sample_id: str = Field(pattern=r"^verifier-[a-zA-Z0-9._-]{4,100}$")
    case_group_id: str = Field(pattern=r"^case-[a-zA-Z0-9._-]{4,100}$")
    task_category: Literal[
        "correct_answer",
        "hallucinated_answer",
        "missing_warning",
        "wrong_drug",
        "changed_triage",
        "invalid_citation",
        "cautious_answer",
    ]
    locale: str = Field(pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")
    deidentified: bool
    provenance: DataProvenance
    expert_review: ExpertReview
    question: str = Field(min_length=1, max_length=4000)
    patient_context: dict[str, Any] = Field(default_factory=dict)
    immutable_claims: list[str] = Field(min_length=1, max_length=64)
    evidence: list[EvidenceItem] = Field(default_factory=list, max_length=32)
    candidate_answer: str = Field(min_length=1, max_length=12000)
    target: VerifierTarget


TrainingSample = AnswerTrainingSample | VerifierTrainingSample


def parse_training_sample(value: dict[str, Any]) -> TrainingSample:
    role = value.get("role")
    if role == "answer":
        return AnswerTrainingSample.model_validate(value)
    if role == "verifier":
        return VerifierTrainingSample.model_validate(value)
    raise ValueError("training sample role must be answer or verifier")
