from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProductVerificationRequest(BaseModel):
    raw_code: str = Field(min_length=1, max_length=2048)


class ProductVerificationResponse(BaseModel):
    request_id: str
    verification_status: Literal[
        "registry_match",
        "suspected_counterfeit",
        "unknown",
        "recalled",
        "invalid",
    ]
    product: dict[str, Any] | None = None
    decoded: dict[str, str] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    disclaimer: str = "Kết quả chỉ đối chiếu registry và không thể tự xác nhận tính thật vật lý của sản phẩm."
