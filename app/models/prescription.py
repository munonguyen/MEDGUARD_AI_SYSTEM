from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.chat import GroundedAnswer
from app.models.common import DisclaimerMixin


class PrescriptionExtractAccepted(DisclaimerMixin):
    request_id: str
    job_id: str
    status: Literal["queued"] = "queued"
    estimated_seconds: int = 8
    poll_url: str
    answer: GroundedAnswer | None = None


class PrescriptionExtractFingerprint(BaseModel):
    patient_ref: str = Field(min_length=1, max_length=128)
    catalog_ref: str | None = None
    conversation_id: str | None = None
    message: str | None = None
    image_sha256: str
    image_size_bytes: int

    @field_validator("patient_ref")
    @classmethod
    def patient_ref_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("patient_ref must not be blank")
        return value


class JobActionFingerprint(BaseModel):
    job_id: str = Field(min_length=1, max_length=128)
    approved: bool | None = None


class JobStatusResponse(DisclaimerMixin):
    request_id: str
    job_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    review_status: Literal[
        "PENDING_REVIEW",
        "COMPLETED",
        "FAILED",
        "CONFIRMED_BY_PHARMACIST",
        "REJECTED_BY_PHARMACIST",
    ] = "PENDING_REVIEW"
    result: dict | None = None
    error_code: str | None = None
