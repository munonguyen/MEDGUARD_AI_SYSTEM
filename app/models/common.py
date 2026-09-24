from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Status(str, Enum):
    ok = "ok"
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    low_confidence = "low_confidence"
    pending_review = "pending_review"
    needs_review = "needs_review"
    unknown = "unknown"


class DisclaimerMixin(BaseModel):
    disclaimer: str = Field(default="Kết quả chỉ mang tính hỗ trợ lâm sàng, không thay thế bác sĩ.")


class Trace(BaseModel):
    request_id: str
    tenant_id: str
    rule_version: str
    knowledge_version: str = "dev-fixture@pha0"
    model_version: str = "deterministic@pha0"
    latency_ms: int
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    request_id: str
    details: dict[str, Any] = Field(default_factory=dict)
