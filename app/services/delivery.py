from __future__ import annotations

from hashlib import sha256
from hmac import new as hmac_new
from json import dumps
from time import perf_counter, time
from uuid import uuid4

from app.core.config import settings
from app.core.context import RequestContext
from app.models.common import Status, Trace
from app.models.delivery import DeliveryEnvelope, DeliveryRequest, DeliveryResponse
from app.services.audit import AuditEvent, audit_store


def _signature(payload: dict) -> tuple[str, str]:
    timestamp = str(int(time()))
    body = dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hmac_new(
        settings.delivery_hmac_secret.encode("utf-8"),
        f"{timestamp}.{body}".encode("utf-8"),
        sha256,
    ).hexdigest()
    return timestamp, digest


def prepare_delivery(payload: DeliveryRequest, ctx: RequestContext) -> DeliveryResponse:
    start = perf_counter()
    event_id = f"evt_{uuid4().hex[:16]}"
    envelope_body = {
        "event_name": payload.event_name,
        "tenant_id": ctx.tenant_id,
        "request_id": ctx.request_id,
        "body": payload.body,
    }
    headers: dict[str, str] = {}
    signed = False
    if payload.channel == "webhook":
        timestamp, signature = _signature(envelope_body)
        headers = {
            "X-MedGuard-Timestamp": timestamp,
            "X-MedGuard-Signature": f"sha256={signature}",
            "X-Request-Id": ctx.request_id,
        }
        signed = True
    envelope = DeliveryEnvelope(
        request_id=ctx.request_id,
        event_id=event_id,
        channel=payload.channel,
        target_ref=payload.target_ref,
        headers=headers,
        body=envelope_body,
        signed=signed,
    )
    response = DeliveryResponse(
        request_id=ctx.request_id,
        status=Status.ok,
        envelope=envelope,
        summary="Envelope kết quả đã được chuẩn bị để chuyển tiếp theo kênh đã chọn.",
        trace=Trace(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            rule_version="delivery-envelope@pha0",
            latency_ms=int((perf_counter() - start) * 1000),
            details={"channel": payload.channel, "signed": signed},
        ),
    )
    audit_store.append(
        AuditEvent(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            action="delivery.prepare",
            payload_type=payload.__class__.__name__,
            metadata={"channel": payload.channel, "signed": signed},
        )
    )
    return response
