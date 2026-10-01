from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    tenant_id: str
    idempotency_key: str
    role: str = "service"
