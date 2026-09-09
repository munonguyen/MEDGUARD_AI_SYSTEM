from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.common import DisclaimerMixin, Status, Trace


class DeliveryRequest(BaseModel):
    event_name: str = Field(min_length=1)
    channel: Literal["webhook", "sse", "notification"]
    target_ref: str | None = None
    body: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class DeliveryEnvelope(BaseModel):
    request_id: str
    event_id: str
    channel: Literal["webhook", "sse", "notification"]
    target_ref: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] = Field(default_factory=dict)
    signed: bool = False


class DeliveryResponse(DisclaimerMixin):
    request_id: str
    status: Status = Status.ok
    envelope: DeliveryEnvelope
    summary: str
    trace: Trace
