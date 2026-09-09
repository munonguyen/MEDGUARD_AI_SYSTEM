from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class CircuitStatusResponse(BaseModel):
    circuit_state: str
    latency_ms: int
    error_rate: float
    failure_count: int = 0
    total_requests: int = 0


class ReadinessCheck(BaseModel):
    name: str
    status: Literal["pass", "warn", "fail"]
    detail: str
    required_for_production: bool = True


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded"]
    service: str
    environment: str
    production_ready: bool
    checks: list[ReadinessCheck] = Field(default_factory=list)
