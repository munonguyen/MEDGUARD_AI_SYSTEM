from __future__ import annotations

from time import perf_counter

from app.core.context import RequestContext
from app.models.common import Status, Trace
from app.models.safety import SafetyRequest, SafetyResponse
from app.knowledge.loader import knowledge
from app.services.audit import AuditEvent, audit_store
from app.services.rules import safety_rules


def evaluate_safety(payload: SafetyRequest, ctx: RequestContext) -> SafetyResponse:
    start = perf_counter()
    rule = safety_rules(payload)
    response = SafetyResponse(
        request_id=ctx.request_id,
        status=Status.ok,
        overall_risk=rule.overall_risk,  # type: ignore[arg-type]
        requires_human_review=rule.requires_human_review,
        warnings=rule.warnings,
        unknown_ingredients=rule.unknown_ingredients,
        trace=Trace(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            rule_version="safety-rules@pha0",
            knowledge_version=knowledge.version_string(),
            latency_ms=int((perf_counter() - start) * 1000),
            details={
                "basis": "structured_table",
                "knowledge_integrity": knowledge.integrity_report(),
            },
        ),
    )
    audit_store.append(
        AuditEvent(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            action="safety.evaluate",
            payload_type=payload.__class__.__name__,
            metadata={"overall_risk": response.overall_risk, "requires_human_review": response.requires_human_review},
        )
    )
    return response
