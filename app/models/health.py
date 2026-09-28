from typing import Literal

from pydantic import BaseModel, Field, model_validator


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

    @model_validator(mode="after")
    def include_external_production_evidence(self) -> "ReadinessResponse":
        """Make operational evidence part of the same production-readiness truth.

        Runtime health checks alone cannot prove backup/restore, disaster recovery,
        security testing, provider data controls, or live shadow evaluation. The
        V19 registry is therefore appended as a required check at the response
        contract boundary. Existing callers of build_readiness() automatically
        inherit the gate without duplicating readiness logic or handling secrets.
        """
        if not any(check.name == "external_production_evidence" for check in self.checks):
            from app.services.external_evidence_registry import external_evidence_readiness

            evidence_status, evidence_detail = external_evidence_readiness()
            self.checks.append(
                ReadinessCheck(
                    name="external_production_evidence",
                    status=evidence_status,
                    detail=evidence_detail,
                    required_for_production=True,
                )
            )

        self.production_ready = all(
            check.status == "pass"
            for check in self.checks
            if check.required_for_production
        )
        self.status = "ready" if self.production_ready else "degraded"
        return self
