from __future__ import annotations

from time import perf_counter

from app.core.context import RequestContext
from app.models.common import Trace
from app.models.queue import (
    PrioritizedQueueItem,
    QueuePrioritizeRequest,
    QueuePrioritizeResponse,
)
from app.services.audit import AuditEvent, audit_store


def _severity_score(item) -> tuple[float, list[str]]:
    rationale: list[str] = []
    if item.emergency_flag or item.urgency == "EMERGENCY":
        rationale.append("emergency_flag_or_urgency")
        base = 100.0
    elif item.urgency == "URGENT":
        rationale.append("urgent_urgency")
        base = 70.0
    else:
        rationale.append("routine_urgency")
        base = 40.0

    if item.esi_level is not None:
        base += (6 - item.esi_level) * 4
        rationale.append("esi_level")

    # Aging helps break ties but is capped so waiting time cannot outrank an
    # emergency solely through queue delay.
    aging = min(item.wait_minutes, 120) / 20
    if aging:
        rationale.append("wait_time_capped")
    return base + aging, rationale


def prioritize_queue(payload: QueuePrioritizeRequest, ctx: RequestContext) -> QueuePrioritizeResponse:
    start = perf_counter()
    scored = []
    for index, item in enumerate(payload.items):
        score, rationale = _severity_score(item)
        scored.append((score, index, item, rationale))

    scored.sort(key=lambda value: (-value[0], value[1]))
    result = [
        PrioritizedQueueItem(
            patient_ref=item.patient_ref,
            rank=rank,
            priority_score=round(score, 2),
            priority_band="EMERGENCY" if item.emergency_flag else item.urgency,
            rationale=rationale,
        )
        for rank, (score, _, item, rationale) in enumerate(scored, start=1)
    ]
    response = QueuePrioritizeResponse(
        request_id=ctx.request_id,
        items=result,
        trace=Trace(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            rule_version="queue-priority-rules@pha0",
            latency_ms=int((perf_counter() - start) * 1000),
            details={"ordering": "severity_then_esi_then_capped_wait_then_input_order"},
        ),
    )
    audit_store.append(
        AuditEvent(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            action="queue.prioritize",
            payload_type=payload.__class__.__name__,
            metadata={"item_count": len(result), "top_priority": result[0].priority_band},
        )
    )
    return response
