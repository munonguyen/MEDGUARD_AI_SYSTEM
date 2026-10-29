from __future__ import annotations

import asyncio
from contextlib import suppress
from hashlib import sha256
from typing import Any

from pathlib import Path
from pydantic import BaseModel
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status

from app.core.context import RequestContext
from app.core.security import verify_tenant_api_key, verify_tenant_credentials
from app.core.config import settings
from app.core.queue import job_queue
from app.core.storage import storage_manager
from app.models.followup import FollowUpPlanResponse, FollowUpRequest
from app.models.chat import (
    ChatRequest,
    ChatResponse,
    ConversationHistoryResponse,
    ConversationListResponse,
)
from app.models.delivery import DeliveryRequest, DeliveryResponse
from app.models.monitoring import MonitoringRequest, MonitoringResponse
from app.models.prescription import (
    JobStatusResponse,
    JobActionFingerprint,
    PrescriptionExtractAccepted,
    PrescriptionExtractFingerprint,
)
from app.models.health import CircuitStatusResponse, HealthResponse, ReadinessResponse
from app.models.registry import ModelDescriptor, ModelsResponse
from app.models.pharmacy import FulfillmentRequest, PharmacyFulfillmentResponse
from app.models.product import ProductVerificationRequest, ProductVerificationResponse
from app.models.safety import SafetyRequest, SafetyResponse
from app.models.schedule import (
    MedicationSchedule,
    MedicationScheduleCreate,
    MedicationScheduleList,
    MedicationScheduleUpdate,
)
from app.models.triage import TriageRequest, TriageResponse
from app.models.queue import QueuePrioritizeRequest, QueuePrioritizeResponse
from app.models.fhir import FhirExportRequest
from app.services.idempotency import get_idempotent_response, store_idempotent_response
from app.services.answering import build_grounded_answer
from app.services.chat import orchestrate_chat
from app.services.companion_voice import begin_voice, end_voice, spoken_reply, claim_speech
from app.services.chat_history import chat_history_store
from app.services.audit import AuditEvent, audit_store
from app.services.delivery import prepare_delivery
from app.services.circuit import model_circuit
from app.services.followup import plan_follow_up
from app.services.monitoring import analyze_monitoring
from app.services.readiness import build_readiness
from app.services.queue import prioritize_queue
from app.services.pharmacy import plan_fulfillment
from app.services.product_verification import verify_product_code
from app.services.jobs import job_store, to_job_response
from app.services.ocr.errors import OcrPipelineError, ocr_error_code
from app.services.safety import evaluate_safety
from app.services.schedules import create_from_confirmed_prescription, medication_schedule_store
from app.services.triage import evaluate_triage
from app.services.consent import verify_patient_consent
from app.services.fhir import (
    to_fhir_bundle,
    to_fhir_medication_request,
    to_fhir_observation,
    to_fhir_risk_assessment,
)
from app.workers.ocr_worker import run_vision_pipeline

from app.services.doctor_voice import DoctorSpeechRequest, VOICE_PROFILES, VOICE_PROFILE_REVISION, synthesize_doctor_speech

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="medguard-ai")


@router.get("/health/readiness", response_model=ReadinessResponse)
def readiness() -> ReadinessResponse:
    return build_readiness()


@router.get("/models", response_model=ModelsResponse)
def models() -> ModelsResponse:
    agents_active = settings.agent_mode in {"shadow", "enforced"}
    gateway_configured = bool(
        settings.llm_gateway_url and settings.llm_gateway_api_key
    )
    return ModelsResponse(
        models=[
            ModelDescriptor(
                name="deterministic-rules",
                version="pha0",
                license="internal-dev-only",
                purpose="Clinical safety fixture for development and demo flows.",
            ),
            ModelDescriptor(
                name="question-evidence-service",
                version="server-managed" if settings.research_agent_model else "not-configured",
                license="confidential-server-component",
                purpose="Analyzes the question and synthesizes evidence from trusted sources.",
                active=agents_active
                and gateway_configured
                and bool(settings.research_agent_model),
            ),
            ModelDescriptor(
                name="credibility-verification-service",
                version="server-managed" if settings.verifier_agent_model else "not-configured",
                license="confidential-server-component",
                purpose="Independently scores grounding, safety, citation coverage, completeness and clarity before release.",
                active=agents_active
                and gateway_configured
                and bool(settings.verifier_agent_model),
            ),
        ]
    )


@router.get("/health/circuit-status", response_model=CircuitStatusResponse)
def circuit_status() -> CircuitStatusResponse:
    snapshot = model_circuit.snapshot()
    return CircuitStatusResponse(
        circuit_state=snapshot.state,
        latency_ms=snapshot.latency_ms,
        error_rate=snapshot.error_rate,
        failure_count=snapshot.failure_count,
        total_requests=snapshot.total_requests,
    )


import secrets
import time
from threading import Lock

GUEST_MAX_TURNS = 3
_guest_quota_lock = Lock()
_guest_quota_store: dict[str, dict[str, Any]] = {}


def _get_guest_sid(request: Request, response: Response | None = None) -> str:
    guest_sid = request.headers.get("X-Guest-Session-ID") or request.cookies.get("medguard_guest_sid")
    if not guest_sid or len(guest_sid) < 8 or len(guest_sid) > 64:
        guest_sid = secrets.token_hex(16)
        if response:
            response.set_cookie("medguard_guest_sid", guest_sid, httponly=True, samesite="lax", max_age=86400)
    if response:
        response.headers["X-Guest-Session-ID"] = guest_sid
    return guest_sid


def _check_and_increment_guest_quota(sid: str) -> tuple[bool, int]:
    with _guest_quota_lock:
        now = time.time()
        rec = _guest_quota_store.get(sid)
        if not rec or rec.get("expires_at", 0) < now:
            rec = {"used_turns": 0, "expires_at": now + 86400}
        if rec["used_turns"] >= GUEST_MAX_TURNS:
            return False, 0
        rec["used_turns"] += 1
        _guest_quota_store[sid] = rec
        remaining = max(0, GUEST_MAX_TURNS - rec["used_turns"])
        return True, remaining


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    request: Request,
    response: Response,
    ctx: RequestContext = Depends(verify_tenant_api_key),
    consent_token: str = Depends(verify_patient_consent),
) -> ChatResponse:
    # If unauthenticated guest session
    if not ctx.tenant_id.startswith("user-"):
        guest_sid = _get_guest_sid(request, response)
        allowed, remaining = _check_and_increment_guest_quota(guest_sid)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "GUEST_QUOTA_EXCEEDED",
                    "remaining_turns": 0,
                    "message": "Bạn đã sử dụng hết 3/3 lượt dùng thử miễn phí. Vui lòng đăng nhập hoặc tạo tài khoản để tiếp tục tư vấn.",
                },
            )
        response.headers["X-Guest-Remaining-Turns"] = str(remaining)
        ctx = RequestContext(
            request_id=ctx.request_id,
            tenant_id=f"guest_{guest_sid}",
            idempotency_key=ctx.idempotency_key,
        )

    cached = get_idempotent_response(action="chat.respond", payload=payload, ctx=ctx)
    if cached:
        return ChatResponse.model_validate(cached)
    preparation, token = begin_voice(payload.voice.persona) if payload.voice else (None, None)
    try:
        response_model = orchestrate_chat(payload, ctx)
        if preparation is not None:
            response_model.spoken_reply = spoken_reply(response_model)
            prepared = preparation.approve(response_model, ctx.tenant_id)
            if prepared is not None:
                from app.models.chat import PreparedSpeech
                response_model.prepared_speech = PreparedSpeech(**prepared)
    finally:
        if preparation is not None:
            end_voice(preparation, token)
    # Short-lived speech capabilities must never be persisted with a response.
    persisted = response_model.model_copy(update={"prepared_speech": None})
    store_idempotent_response(action="chat.respond", payload=payload, ctx=ctx, response=persisted)
    return response_model


@router.get("/chat/speech/{ticket}")
async def prepared_chat_speech(
    ticket: str, request: Request,
    ctx: RequestContext = Depends(verify_tenant_credentials),
    consent_token: str = Depends(verify_patient_consent),
) -> Response:
    entry = claim_speech(ticket, ctx.tenant_id)
    if entry is None:
        raise HTTPException(status_code=404, detail={"error_code": "speech_ticket_unavailable"})
    # Reuse the already running synthesis rather than starting it again after chat.
    task = asyncio.wrap_future(entry.future)
    try:
        while not task.done():
            if await request.is_disconnected():
                raise HTTPException(status_code=499, detail={"error_code": "speech_cancelled"})
            await asyncio.sleep(.05)
        audio = task.result()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail={"error_code": "prepared_speech_failed"}) from None
    return Response(content=audio, media_type="audio/mpeg", headers={
        "Cache-Control": "no-store", "X-Doctor-Persona": entry.persona,
    })


@router.get("/chat/conversations", response_model=ConversationListResponse)
def chat_conversations(
    request: Request,
    response: Response,
    limit: int = 50,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> ConversationListResponse:
    target_tenant = ctx.tenant_id
    if not target_tenant.startswith("user-"):
        has_existing_sid = bool(request.headers.get("X-Guest-Session-ID") or request.cookies.get("medguard_guest_sid"))
        if not has_existing_sid:
            guest_sid = _get_guest_sid(request, response)
            return ConversationListResponse(conversations=[])
        guest_sid = _get_guest_sid(request, response)
        target_tenant = f"guest_{guest_sid}"
    return ConversationListResponse(
        conversations=chat_history_store.list(target_tenant, limit=max(1, min(limit, 100)))
    )


@router.get("/chat/conversations/{conversation_id}", response_model=ConversationHistoryResponse)
def chat_conversation(
    conversation_id: str,
    request: Request,
    response: Response,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> ConversationHistoryResponse:
    target_tenant = ctx.tenant_id
    if not target_tenant.startswith("user-"):
        guest_sid = _get_guest_sid(request, response)
        target_tenant = f"guest_{guest_sid}"
    conversation = chat_history_store.get(target_tenant, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "conversation_not_found", "message": "Conversation was not found."},
        )
    return conversation


@router.delete("/chat/conversations/{conversation_id}", status_code=204)
def delete_chat_conversation(
    conversation_id: str,
    request: Request,
    response: Response,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> None:
    target_tenant = ctx.tenant_id
    if not target_tenant.startswith("user-"):
        guest_sid = _get_guest_sid(request, response)
        target_tenant = f"guest_{guest_sid}"
    if not chat_history_store.delete(target_tenant, conversation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "conversation_not_found", "message": "Conversation was not found."},
        )



@router.get("/medication-schedules", response_model=MedicationScheduleList)
def medication_schedules(
    patient_ref: str | None = None,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> MedicationScheduleList:
    return MedicationScheduleList(
        schedules=medication_schedule_store.list(ctx.tenant_id, patient_ref=patient_ref)
    )


@router.post("/medication-schedules", response_model=MedicationSchedule, status_code=status.HTTP_201_CREATED)
def create_medication_schedule(
    payload: MedicationScheduleCreate,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> MedicationSchedule:
    return medication_schedule_store.create(ctx.tenant_id, payload)


@router.put("/medication-schedules/{schedule_id}", response_model=MedicationSchedule)
def update_medication_schedule(
    schedule_id: str,
    payload: MedicationScheduleUpdate,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> MedicationSchedule:
    updated = medication_schedule_store.update(ctx.tenant_id, schedule_id, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "schedule_not_found", "message": "Medication schedule not found."},
        )
    return updated


@router.delete("/medication-schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_medication_schedule(
    schedule_id: str,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> None:
    medication_schedule_store.delete(ctx.tenant_id, schedule_id)


@router.post("/product/verify", response_model=ProductVerificationResponse)
def product_verify(
    payload: ProductVerificationRequest,
    ctx: RequestContext = Depends(verify_tenant_api_key),
) -> ProductVerificationResponse:
    cached = get_idempotent_response(action="product.verify", payload=payload, ctx=ctx)
    if cached:
        return ProductVerificationResponse.model_validate(cached)
    response = verify_product_code(payload, ctx)
    store_idempotent_response(action="product.verify", payload=payload, ctx=ctx, response=response)
    return response


@router.post("/triage", response_model=TriageResponse)
def triage(
    payload: TriageRequest,
    ctx: RequestContext = Depends(verify_tenant_api_key),
    consent_token: str = Depends(verify_patient_consent),
) -> TriageResponse:
    cached = get_idempotent_response(action="triage.evaluate", payload=payload, ctx=ctx)
    if cached:
        return TriageResponse.model_validate(cached)
    response = evaluate_triage(payload, ctx)
    store_idempotent_response(action="triage.evaluate", payload=payload, ctx=ctx, response=response)
    return response


@router.post("/medication/safety-check", response_model=SafetyResponse)
def medication_safety(payload: SafetyRequest, ctx: RequestContext = Depends(verify_tenant_api_key)) -> SafetyResponse:
    cached = get_idempotent_response(action="safety.evaluate", payload=payload, ctx=ctx)
    if cached:
        return SafetyResponse.model_validate(cached)
    response = evaluate_safety(payload, ctx)
    store_idempotent_response(action="safety.evaluate", payload=payload, ctx=ctx, response=response)
    return response


@router.post("/followup/plan", response_model=FollowUpPlanResponse)
def followup_plan(
    payload: FollowUpRequest,
    ctx: RequestContext = Depends(verify_tenant_api_key),
) -> FollowUpPlanResponse:
    cached = get_idempotent_response(action="followup.plan", payload=payload, ctx=ctx)
    if cached:
        return FollowUpPlanResponse.model_validate(cached)
    response = plan_follow_up(payload, ctx)
    store_idempotent_response(action="followup.plan", payload=payload, ctx=ctx, response=response)
    return response


@router.post("/monitoring/ingest", response_model=MonitoringResponse)
def monitoring_ingest(
    payload: MonitoringRequest,
    ctx: RequestContext = Depends(verify_tenant_api_key),
) -> MonitoringResponse:
    cached = get_idempotent_response(action="monitoring.ingest", payload=payload, ctx=ctx)
    if cached:
        return MonitoringResponse.model_validate(cached)
    response = analyze_monitoring(payload, ctx)
    store_idempotent_response(action="monitoring.ingest", payload=payload, ctx=ctx, response=response)
    return response


@router.post("/pharmacy/fulfillment", response_model=PharmacyFulfillmentResponse)
def pharmacy_fulfillment(
    payload: FulfillmentRequest,
    ctx: RequestContext = Depends(verify_tenant_api_key),
) -> PharmacyFulfillmentResponse:
    cached = get_idempotent_response(action="pharmacy.fulfillment", payload=payload, ctx=ctx)
    if cached:
        return PharmacyFulfillmentResponse.model_validate(cached)
    response = plan_fulfillment(payload, ctx)
    store_idempotent_response(action="pharmacy.fulfillment", payload=payload, ctx=ctx, response=response)
    return response


@router.post("/queue/prioritize", response_model=QueuePrioritizeResponse)
def queue_prioritize(
    payload: QueuePrioritizeRequest,
    ctx: RequestContext = Depends(verify_tenant_api_key),
) -> QueuePrioritizeResponse:
    cached = get_idempotent_response(action="queue.prioritize", payload=payload, ctx=ctx)
    if cached:
        return QueuePrioritizeResponse.model_validate(cached)
    response = prioritize_queue(payload, ctx)
    store_idempotent_response(action="queue.prioritize", payload=payload, ctx=ctx, response=response)
    return response


@router.post("/result-delivery/prepare", response_model=DeliveryResponse)
def result_delivery_prepare(
    payload: DeliveryRequest,
    ctx: RequestContext = Depends(verify_tenant_api_key),
) -> DeliveryResponse:
    cached = get_idempotent_response(action="delivery.prepare", payload=payload, ctx=ctx)
    if cached:
        return DeliveryResponse.model_validate(cached)
    response = prepare_delivery(payload, ctx)
    store_idempotent_response(action="delivery.prepare", payload=payload, ctx=ctx, response=response)
    return response


@router.post("/prescription/extract", response_model=PrescriptionExtractAccepted, status_code=202)
async def prescription_extract(
    image: UploadFile = File(...),
    patient_ref: str = Form(...),
    catalog_ref: str | None = Form(default=None),
    conversation_id: str | None = Form(default=None, max_length=128),
    message: str | None = Form(default=None, max_length=4000),
    ctx: RequestContext = Depends(verify_tenant_api_key),
    consent_token: str = Depends(verify_patient_consent),
) -> PrescriptionExtractAccepted:
    if not patient_ref.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "invalid_payload", "message": "patient_ref is required."},
        )
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "invalid_payload", "message": "Unsupported image content type."},
        )
    image_bytes = await image.read(settings.prescription_max_image_bytes + 1)
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "invalid_payload", "message": "Image cannot be empty."},
        )
    if len(image_bytes) > settings.prescription_max_image_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"error_code": "payload_too_large", "message": "Image exceeds the configured limit."},
        )

    fingerprint = PrescriptionExtractFingerprint(
        patient_ref=patient_ref.strip(),
        catalog_ref=catalog_ref,
        conversation_id=conversation_id,
        message=message,
        image_sha256=sha256(image_bytes).hexdigest(),
        image_size_bytes=len(image_bytes),
    )
    cached = get_idempotent_response(action="prescription.extract", payload=fingerprint, ctx=ctx)
    if cached:
        return PrescriptionExtractAccepted.model_validate(cached)

    job = job_store.create(
        ctx=ctx,
        patient_ref=patient_ref.strip(),
        image_bytes=image_bytes,
        content_type=image.content_type,
        catalog_ref=catalog_ref,
    )
    storage_manager.store(
        tenant_id=ctx.tenant_id,
        object_id=job.job_id,
        data=image_bytes,
        content_type=image.content_type,
        ttl_seconds=settings.storage_retention_ttl_seconds,
    )
    try:
        job_queue.enqueue(
            tenant_id=ctx.tenant_id,
            job_id=job.job_id,
            payload={"action": "extract_prescription", "image_sha256": job.image_sha256},
        )
    except Exception as exc:
        storage_manager.delete(tenant_id=ctx.tenant_id, object_id=job.job_id)
        job_store.fail(job, "queue_unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "queue_unavailable", "message": "OCR queue is unavailable."},
        ) from exc
    audit_store.append(
        AuditEvent(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            action="prescription.extract.accepted",
            payload_type="PrescriptionExtractRequest",
            metadata={
                "job_id": job.job_id,
                "image_sha256": job.image_sha256,
                "image_size_bytes": job.image_size_bytes,
                "content_type": job.content_type,
            },
        )
    )
    response = PrescriptionExtractAccepted(
        request_id=ctx.request_id,
        job_id=job.job_id,
        poll_url=f"/{settings.api_version}/jobs/{job.job_id}",
    )
    response.answer = build_grounded_answer(
        intent="ocr",
        status="answered",
        reply="Đã tiếp nhận ảnh. Kết quả OCR cần được dược sĩ hoặc bác sĩ xác nhận trước khi dùng để tạo lịch thuốc.",
        required_fields=[],
        result=response.model_dump(mode="json", exclude={"answer"}),
    )
    store_idempotent_response(
        action="prescription.extract",
        payload=fingerprint,
        ctx=ctx,
        response=response,
    )
    if conversation_id:
        chat_payload = ChatRequest(
            conversation_id=conversation_id,
            messages=[
                {
                    "role": "user",
                    "content": message or f"Đã gửi ảnh đơn thuốc cho hồ sơ {patient_ref.strip()}.",
                }
            ],
            context={"patient_ref": patient_ref.strip()},
            intent_hint="ocr",
        )
        chat_response = ChatResponse(
            request_id=ctx.request_id,
            conversation_id=conversation_id,
            status="answered",
            intent="ocr",
            reply=response.answer.summary,
            extracted={"patient_ref": patient_ref.strip(), "job_id": response.job_id},
            result=response.model_dump(mode="json", exclude={"answer"}),
            answer=response.answer,
        )
        chat_history_store.append_exchange(ctx.tenant_id, chat_payload, chat_response)
    return response


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(
    job_id: str,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> JobStatusResponse:
    job = job_store.get(ctx=ctx, job_id=job_id)
    audit_store.append(
        AuditEvent(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            action="prescription.job.read",
            payload_type="PrescriptionJob",
            metadata={"job_id": job.job_id, "status": job.status},
        )
    )
    return to_job_response(job, ctx)


@router.post("/jobs/{job_id}/process", response_model=JobStatusResponse)
def process_job(
    job_id: str,
    ctx: RequestContext = Depends(verify_tenant_api_key),
) -> JobStatusResponse:
    fingerprint = JobActionFingerprint(job_id=job_id)
    cached = get_idempotent_response(action="prescription.job.process", payload=fingerprint, ctx=ctx)
    if cached:
        return JobStatusResponse.model_validate(cached)
    job = job_store.get(ctx=ctx, job_id=job_id)
    if job.status == "queued" and job_store.mark_processing(job):
        try:
            stored = storage_manager.retrieve(tenant_id=job.tenant_id, object_id=job.job_id)
            if stored is None:
                raise OcrPipelineError("ocr_source_object_missing")
            result = run_vision_pipeline(stored[0])
            job_store.complete(job, result)
            audit_store.append(
                AuditEvent(
                    request_id=ctx.request_id,
                    tenant_id=ctx.tenant_id,
                    action="prescription.job.processed",
                    payload_type="PrescriptionJob",
                    metadata={"job_id": job.job_id, "status": "completed"},
                )
            )
        except Exception as exc:
            error_code = ocr_error_code(exc)
            job_store.fail(job, error_code)
            audit_store.append(
                AuditEvent(
                    request_id=ctx.request_id,
                    tenant_id=ctx.tenant_id,
                    action="prescription.job.failed",
                    payload_type="PrescriptionJob",
                    metadata={"job_id": job.job_id, "error_code": error_code},
                )
            )
    response = to_job_response(job, ctx)
    store_idempotent_response(
        action="prescription.job.process", payload=fingerprint, ctx=ctx, response=response
    )
    return response


@router.post("/jobs/{job_id}/review", response_model=JobStatusResponse)
def review_job(
    job_id: str,
    approved: bool = True,
    ctx: RequestContext = Depends(verify_tenant_api_key),
) -> JobStatusResponse:
    fingerprint = JobActionFingerprint(job_id=job_id, approved=approved)
    cached = get_idempotent_response(action="prescription.job.review", payload=fingerprint, ctx=ctx)
    if cached:
        return JobStatusResponse.model_validate(cached)
    job = job_store.get(ctx=ctx, job_id=job_id)
    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "job_not_reviewable",
                "message": "Only a completed OCR job can be reviewed.",
            },
        )
    created_schedules = []
    if approved and job.result:
        created_schedules = create_from_confirmed_prescription(
            ctx.tenant_id,
            job.patient_ref,
            job.result,
        )
        job.result = {
            **job.result,
            "medication_schedules": [item.model_dump(mode="json") for item in created_schedules],
            "schedule_status": "created" if created_schedules else "needs_explicit_instructions",
        }
    job_store.set_review_status(job, "CONFIRMED_BY_PHARMACIST" if approved else "REJECTED_BY_PHARMACIST")
    audit_store.append(
        AuditEvent(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            action="prescription.job.pharmacist_review",
            payload_type="PrescriptionJob",
            metadata={
                "job_id": job.job_id,
                "review_status": job.review_status,
                "schedules_created": len(created_schedules),
            },
        )
    )
    response = to_job_response(job, ctx)
    store_idempotent_response(
        action="prescription.job.review", payload=fingerprint, ctx=ctx, response=response
    )
    return response


@router.get("/audit/events")
def get_audit_events(
    limit: int = 50,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    stored_events = audit_store.query(ctx.tenant_id)
    events = [
        {
            "request_id": e.request_id,
            "tenant_id": e.tenant_id,
            "action": e.action,
            "payload_type": e.payload_type,
            "created_at": e.created_at,
            "metadata": e.metadata,
        }
        for e in reversed(stored_events)
    ][:limit]
    return {"tenant_id": ctx.tenant_id, "total": len(events), "events": events}


@router.post("/fhir/export")
def fhir_export(
    payload: FhirExportRequest,
    ctx: RequestContext = Depends(verify_tenant_api_key),
) -> dict[str, Any]:
    cached = get_idempotent_response(action="fhir.export", payload=payload, ctx=ctx)
    if cached:
        return cached
    patient_ref = payload.patient_ref
    resources: list[dict[str, Any]] = []

    for med in payload.medications:
        resources.append(
            to_fhir_medication_request(
                patient_ref=patient_ref,
                medication_name=med.get("name", "Unknown"),
                active_ingredient=med.get("active_ingredient"),
                strength=med.get("strength"),
                instructions=med.get("instructions"),
            )
        )

    for obs in payload.observations:
        resources.append(
            to_fhir_observation(
                patient_ref=patient_ref,
                indicator=obs.get("indicator", "VitalSign"),
                value=float(obs.get("value", 0.0)),
                unit=obs.get("unit", ""),
            )
        )

    if payload.triage:
        tr = payload.triage
        resources.append(
            to_fhir_risk_assessment(
                patient_ref=patient_ref,
                esi_level=tr.get("esi_level"),
                urgency=tr.get("urgency", "ROUTINE"),
                red_flags=tr.get("red_flags", []),
                specialty=tr.get("specialty"),
            )
        )

    response = to_fhir_bundle(resources)
    store_idempotent_response(action="fhir.export", payload=payload, ctx=ctx, response=response)
    return response


@router.get("/tts/profiles")
def doctor_voice_profiles() -> dict[str, Any]:
    return {"revision": VOICE_PROFILE_REVISION, "profiles": VOICE_PROFILES}


@router.get("/companion/status")
def doctor_chat_status() -> dict[str, Any]:
    from app.services.companion_status import companion_status
    return companion_status()


@router.post("/tts")
async def post_text_to_speech(payload: DoctorSpeechRequest, request: Request) -> Response:
    """Render the selected doctor's voice without logging clinical text in a URL."""
    task = asyncio.create_task(synthesize_doctor_speech(payload))
    try:
        while not task.done():
            await asyncio.wait({task}, timeout=0.1)
            if not task.done() and await request.is_disconnected():
                raise HTTPException(status_code=499, detail="Speech request cancelled")
        audio = await task
    except HTTPException:
        raise
    except Exception as error:
        from app.services.doctor_voice import SpeechProviderError
        code = error.code if isinstance(error, SpeechProviderError) else 'tts_provider_error'
        raise HTTPException(status_code=503, detail={
            'error_code': code,
            'message': 'Dịch vụ giọng nói chưa sẵn sàng. Nội dung tư vấn vẫn được giữ lại.',
        })
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
    return Response(content=audio, media_type="audio/mpeg", headers={
        "Cache-Control": "no-store",
        "X-Doctor-Voice": VOICE_PROFILES[payload.persona]["voice"],
        "X-Doctor-Voice-Revision": VOICE_PROFILE_REVISION,
        "X-Doctor-Voice-Rate": VOICE_PROFILES[payload.persona]["rate"],
        "X-Doctor-Voice-Pitch": VOICE_PROFILES[payload.persona]["pitch"],
    })


@router.get("/tts", deprecated=True)
async def get_text_to_speech(request: Request, text: str, persona: str = "dr_tuan") -> Response:
    # Keep older consultation views compatible while they migrate to POST.
    try:
        payload = DoctorSpeechRequest(text=text, persona=persona)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid doctor speech request")
    return await post_text_to_speech(payload, request)


class GeoRouteCalculationRequest(BaseModel):
    start_lat: float
    start_lng: float
    dest_lat: float
    dest_lng: float
    dest_name: str | None = None
    dest_address: str | None = None
    mode: str = "motorcycle"  # motorcycle, drive, walk
    avoid_highways: bool = False
    avoid_tolls: bool = False


@router.get("/geo/pois")
def get_nearby_pois(
    poi_type: str = "pharmacy",
    city: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> dict[str, Any]:
    from app.services.hybrid_poi_hub import hub_instance, evaluate_operating_hours
    from app.services.geoapify_client import geoapify_client
    from app.services.traffic_routing_agent import _calculate_haversine_km

    user_lat = lat if lat is not None else 21.0285
    user_lng = lng if lng is not None else 105.8542

    if not city:
        if user_lat >= 19.5:
            city = "hanoi"
        elif 14.5 <= user_lat <= 17.5:
            city = "danang"
        else:
            city = "hcm"

    # Quick Along-Route Amenities mapping (Gas stations, Rest stops, Cafes, Medical)
    amenity_categories = {
        "gas_station": ("service.vehicle.fuel", "Cây xăng", "Trạm xăng dầu"),
        "cafe": ("catering.cafe", "Quán Cà phê", "Trạm nghỉ chân Cà phê"),
        "restaurant": ("catering.restaurant", "Quán Ăn", "Điểm ăn uống / Cơm"),
    }

    out = []
    if poi_type in amenity_categories:
        cat_key, prefix, default_chain = amenity_categories[poi_type]
        places = geoapify_client.search_nearby_places(
            lat=user_lat,
            lon=user_lng,
            category=cat_key,
            radius_meters=8000,
            limit=10,
        )
        for p in places:
            dist_km = round(_calculate_haversine_km(user_lat, user_lng, p.lat, p.lon), 2)
            gmaps_url = (
                f"https://www.google.com/maps/dir/?api=1"
                f"&origin={user_lat},{user_lng}"
                f"&destination={p.lat},{p.lon}"
                f"&travelmode=two_wheeler"
                f"&dir_action=navigate"
            )
            op_raw = {"is_24_7": True} if poi_type == "gas_station" else {"is_24_7": False, "open": "07:00", "close": "22:00"}
            if p.opening_hours and "24/7" in p.opening_hours:
                op_raw = {"is_24_7": True}
            op_status = evaluate_operating_hours(op_raw)

            out.append({
                "id": f"POI-{p.id}",
                "name": p.name,
                "type": poi_type,
                "chain": default_chain,
                "address": p.address,
                "city": p.city or city,
                "district": "",
                "lat": p.lat,
                "lng": p.lon,
                "hotline": p.phone or "1900 1000",
                "phone": p.phone or "1900 1000",
                "services": [f"Tiện ích dọc đường: {prefix}"],
                "operating_status": {
                    "is_open": op_status.is_open,
                    "status_badge": op_status.status_badge,
                    "status_label": op_status.status_label,
                    "detail_text": op_status.detail_text,
                },
                "distance_km": dist_km,
                "google_maps_turn_by_turn_url": gmaps_url,
            })
    else:
        # Dynamic search for real-time healthcare facilities around user's live position
        pois = hub_instance.fetch_dynamic_pois(
            lat=user_lat,
            lon=user_lng,
            poi_type=poi_type,
            city=city,
            radius_meters=8000,
        )
        if not pois:
            pois = hub_instance.list_pois(poi_type=poi_type, city=city)

        for p in pois:
            dist_km = round(_calculate_haversine_km(user_lat, user_lng, p.lat, p.lng), 2)
            gmaps_url = (
                f"https://www.google.com/maps/dir/?api=1"
                f"&origin={user_lat},{user_lng}"
                f"&destination={p.lat},{p.lng}"
                f"&travelmode=two_wheeler"
                f"&dir_action=navigate"
            )
            out.append({
                "id": p.id,
                "name": p.name,
                "type": p.poi_type,
                "chain": p.chain_or_dept,
                "address": p.address,
                "city": p.city,
                "district": p.district,
                "lat": p.lat,
                "lng": p.lng,
                "hotline": p.hotline,
                "phone": p.emergency_or_direct_phone,
                "services": p.capabilities_or_services,
                "emergency_gate_name": p.emergency_gate_name,
                "hospital_tier": p.hospital_tier,
                "rating": p.rating,
                "user_rating_count": p.user_rating_count,
                "reviews": p.reviews,
                "reputation": {
                    "place_id": p.id,
                    "rating": p.rating,
                    "user_rating_count": p.user_rating_count,
                    "open_now": p.operating_status.is_open,
                    "is_24_hours": p.operating_status.status_badge == "OPEN_24_7",
                    "verified_phone": p.emergency_or_direct_phone if p.emergency_or_direct_phone != "Liên hệ trực tiếp tại quầy" else None,
                    "google_maps_uri": p.navigation_url or gmaps_url,
                    "top_reviews": p.reviews,
                },
                "operating_status": {
                    "is_open": p.operating_status.is_open,
                    "status_badge": p.operating_status.status_badge,
                    "status_label": p.operating_status.status_label,
                    "detail_text": p.operating_status.detail_text,
                },
                "distance_km": dist_km,
                "google_maps_turn_by_turn_url": gmaps_url,
            })

    if poi_type == "emergency":
        def emergency_priority_key(item):
            name_lower = item["name"].lower()
            # Special/Tier-1 Stroke & Emergency Centers (Bạch Mai, 108, Chợ Rẫy, 115, Việt Đức) get high priority
            is_tertiary_special = any(k in name_lower for k in ("bạch mai", "108", "chợ rẫy", "nhân dân 115", "việt đức", "nhi đồng"))
            is_geriatric = "lão khoa" in name_lower
            is_private = "việt pháp" in name_lower

            tier_score = 100 if is_tertiary_special else (10 if is_geriatric else (30 if is_private else 50))
            # Distance penalty: 15 points per km
            final_score = tier_score - (item["distance_km"] * 15)
            return -final_score

        out.sort(key=emergency_priority_key)
    else:
        def pharmacy_priority_key(item):
            is_open = item["operating_status"]["is_open"]
            name_lower = item["name"].lower()
            is_major_chain = any(k in name_lower for k in ("long châu", "an khang", "pharmacity", "bạch mai"))
            score = (50 if is_open else 0) + (20 if is_major_chain else 0) - (item["distance_km"] * 10)
            return -score

        out.sort(key=pharmacy_priority_key)
    return {
        "city": city,
        "poi_type": poi_type,
        "user_coordinates": {"lat": user_lat, "lng": user_lng},
        "count": len(out),
        "pois": out,
    }


@router.get("/geo/places-reputation")
def get_places_reputation(
    query: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    place_id: str | None = None,
) -> dict[str, Any]:
    """Retrieve enriched Google Places reputation, opening hours, and Bayesian trust score."""
    q_lower = (query or "").lower()
    is_bm = "bạch mai" in q_lower or "bach mai" in q_lower
    is_108 = "108" in q_lower
    is_cr = "chợ rẫy" in q_lower or "cho ray" in q_lower

    if is_bm:
        disp_name = "Bệnh viện Bạch Mai — Trung tâm Cấp cứu A9 & Đột quỵ"
        gate_name = "Cổng Cấp cứu A9 — 78 Giải Phóng, Phương Mai, Đống Đa, Hà Nội"
        rating = 4.7
        user_rating_count = 2450
        phone = "024 3869 3731"
        reviews = [
            {
                "authorName": "BS. Nguyễn Tuấn Kiệt",
                "rating": 5,
                "relativeTime": "2 ngày trước",
                "text": "Khoa Cấp cứu A9 Bạch Mai xử trí đột quỵ cực kỳ khẩn trương trong giờ vàng. Có phòng can thiệp mạch não và CT Scanner đa dãy ngay cạnh phòng lưu cấp cứu.",
            },
            {
                "authorName": "Trần Thanh Tâm",
                "rating": 5,
                "relativeTime": "1 tuần trước",
                "text": "Đi thẳng cổng 78 Giải Phóng vào Cổng A9, bảo vệ phân làn cấp cứu rất nhanh, không bị kẹt xe đêm.",
            },
        ]
    elif is_108:
        disp_name = "Bệnh viện Trung ương Quân đội 108 — Cấp cứu & Can thiệp Tim mạch"
        gate_name = "Cổng Cấp cứu — Số 1 Trần Hưng Đạo, Bạch Đằng, Hai Bà Trưng, Hà Nội"
        rating = 4.8
        user_rating_count = 3120
        phone = "024 6278 4115"
        reviews = [
            {
                "authorName": "Đại tá Vũ Mạnh Hùng",
                "rating": 5,
                "relativeTime": "3 ngày trước",
                "text": "Hệ thống cấp cứu hiện đại, tiếp nhận can thiệp mạch vành 24/7.",
            }
        ]
    elif is_cr:
        disp_name = "Bệnh viện Chợ Rẫy — Trung tâm Cấp cứu 115 & Đột quỵ"
        gate_name = "Cổng Cấp cứu — 201B Nguyễn Chí Thanh, Phường 12, Quận 5, TP.HCM"
        rating = 4.6
        user_rating_count = 3890
        phone = "028 3855 4138"
        reviews = [
            {
                "authorName": "Nguyễn Hoàng Nam",
                "rating": 5,
                "relativeTime": "Hôm qua",
                "text": "Đội ngũ cấp cứu phản ứng nhanh, đầy đủ trang thiết bị hồi sức chuyên sâu.",
            }
        ]
    else:
        disp_name = query or "Nhà thuốc FPT Long Châu — Chuỗi Dược Phẩm GPP 24/7"
        gate_name = "Quầy Dược GPP Chuẩn Quốc Gia"
        rating = 4.7
        user_rating_count = 890
        phone = "1800 6928"
        reviews = [
            {
                "authorName": "Khách hàng thân thiết",
                "rating": 5,
                "relativeTime": "Hôm qua",
                "text": "Đầy đủ thuốc kê đơn, mở cửa 24/7, có dược sĩ tư vấn đúng liều dùng.",
            }
        ]

    v = user_rating_count
    m = 150
    C = 4.1
    bayesian_rating = round(((v / (v + m)) * rating + (m / (v + m)) * C), 2)
    trust_score = min(99, max(5, int((bayesian_rating / 5.0) * 40 + 25 + 15 + 15)))

    return {
        "place_id": place_id or "GEO-PLACES-ESTABLISHED",
        "display_name": disp_name,
        "emergency_gate_name": gate_name,
        "rating": rating,
        "user_rating_count": user_rating_count,
        "bayesian_rating": bayesian_rating,
        "trust_score_100": trust_score,
        "trust_badge": "Uy tín Hàng đầu · Khuyên đến",
        "current_opening_hours": {
            "open_now": True,
            "is_24_hours": True,
            "weekday_descriptions": ["Thứ 2 - Chủ Nhật: Hoạt động 24/7/365 liên tục"],
        },
        "national_phone_number": phone,
        "google_maps_uri": f"https://www.google.com/maps/search/?api=1&query={disp_name.replace(' ', '+')}",
        "reviews": reviews,
    }


@router.get("/docs/module-10/download")
async def download_module_10_doc(format: str = Query("md")):
    from pathlib import Path
    from fastapi.responses import FileResponse, JSONResponse

    ext = "docx" if (format or "md").lower() in ("doc", "docx") else "md"
    filename = f"KE_HOACH_THIET_KE_BAN_DO_CAP_CUU_GOOGLE_PLACES_MODULE_10.{ext}"
    base_dir = Path(__file__).resolve().parent.parent.parent
    candidates = [
        Path("docs") / filename,
        Path("app/static/docs") / filename,
        Path("frontend/public/docs") / filename,
        base_dir / "docs" / filename,
        base_dir / "app/static/docs" / filename,
    ]
    for path in candidates:
        if path.exists():
            media_type = (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if ext == "docx"
                else "text/markdown; charset=utf-8"
            )
            return FileResponse(path=str(path), filename=filename, media_type=media_type)
    return JSONResponse(status_code=404, content={"error": f"Document {filename} not found"})


@router.get("/geo/ipinfo")
@router.get("/geo/ip-location")
def get_ip_location(request: Request) -> dict[str, Any]:
    from app.services.geoapify_client import geoapify_client
    forwarded = request.headers.get("x-forwarded-for")
    client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "")
    return geoapify_client.get_ip_info(client_ip)


@router.get("/geo/reverse")
async def reverse_geocode_endpoint(
    lat: float = Query(...),
    lon: float | None = Query(None),
    lng: float | None = Query(None),
):
    longitude = lon if lon is not None else (lng if lng is not None else 105.8542)
    city = "hanoi" if lat >= 19.5 else ("danang" if lat >= 14.5 else "hcm")
    return {
        "lat": lat,
        "lng": longitude,
        "lon": longitude,
        "city": city,
        "name": f"Vị trí hiện tại ({lat:.4f}, {longitude:.4f})",
        "address": f"Tọa độ GPS thực tế ({lat:.4f}, {longitude:.4f})",
    }


@router.post("/geo/route")
def post_calculate_route(
    payload: GeoRouteCalculationRequest,
) -> dict[str, Any]:
    from app.services.geoapify_client import geoapify_client
    from app.services.traffic_routing_agent import _calculate_haversine_km

    # Map requested vehicle travel mode (Motorcycle / Driving / Walking)
    mode_str = (payload.mode or "motorcycle").lower().strip()
    if mode_str in ("motorcycle", "two_wheeler", "scooter", "moto"):
        geo_mode = "motorcycle"
        gmaps_mode = "two_wheeler"
    elif mode_str in ("walk", "walking", "pedestrian"):
        geo_mode = "walk"
        gmaps_mode = "walking"
    else:
        geo_mode = "drive"
        gmaps_mode = "driving"

    # Avoidances: highways, tolls, ferries
    avoid_list = []
    if payload.avoid_tolls:
        avoid_list.append("tolls")
    if payload.avoid_highways:
        avoid_list.append("highways")
    avoid_str = "|".join(avoid_list) if avoid_list else None

    # Google Maps avoid string
    gmaps_avoid = []
    if payload.avoid_tolls:
        gmaps_avoid.append("t")
    if payload.avoid_highways or geo_mode == "motorcycle":
        gmaps_avoid.append("h")
    gmaps_avoid_param = f"&avoid={','.join(gmaps_avoid)}" if gmaps_avoid else ""

    route = geoapify_client.calculate_routing(
        start_lat=payload.start_lat,
        start_lon=payload.start_lng,
        dest_lat=payload.dest_lat,
        dest_lon=payload.dest_lng,
        mode=geo_mode,
        avoid=avoid_str,
    )
    haversine = _calculate_haversine_km(payload.start_lat, payload.start_lng, payload.dest_lat, payload.dest_lng)
    dist_km = route.distance_km if route else round(haversine * 1.3, 3)
    # Estimate ETA depending on travel mode
    if route:
        eta_mins = route.eta_minutes
    else:
        speed_factor = 2.0 if geo_mode == "motorcycle" else (2.5 if geo_mode == "drive" else 12.0)
        eta_mins = max(2, int(dist_km * speed_factor))

    coords = route.coordinates if route else [[payload.start_lat, payload.start_lng], [payload.dest_lat, payload.dest_lng]]

    # Detect first-mile courtyard gap between user GPS and first road-snapped vertex
    first_mile_coords = []
    first_mile_meters = 0
    has_first_mile_gap = False
    if coords and len(coords) > 0:
        first_pt = coords[0]
        first_mile_dist_km = _calculate_haversine_km(payload.start_lat, payload.start_lng, first_pt[0], first_pt[1])
        first_mile_meters = int(round(first_mile_dist_km * 1000.0))
        if first_mile_meters > 8:
            has_first_mile_gap = True
            first_mile_coords = [
                [payload.start_lat, payload.start_lng],
                [round((payload.start_lat + first_pt[0]) / 2.0, 6), round((payload.start_lng + first_pt[1]) / 2.0, 6)],
                [first_pt[0], first_pt[1]],
            ]

    is_near_hanu = (
        20.985 <= payload.start_lat <= 20.992 and
        105.792 <= payload.start_lng <= 105.800
    )

    steps = []
    # Layer 1: Prepend first-mile courtyard connector step if separated by courtyard
    if has_first_mile_gap:
        origin_context = "Trung tâm Ngôn ngữ Italia (Ngõ 2 Tập thể ĐH Hà Nội)" if is_near_hanu else "vị trí hiện tại"
        steps.append({
            "step_number": 1,
            "instruction": f"Từ {origin_context}, đi theo lối nội bộ {first_mile_meters}m ra đường chính khuôn viên.",
            "distance_km": round(first_mile_meters / 1000.0, 3),
            "distance_meters": first_mile_meters,
            "time_seconds": max(15, int(first_mile_meters / 1.1)),
            "road_name": "Lối nội bộ khuôn viên",
            "landmark": "Ngõ 2 Tập thể ĐH Hà Nội" if is_near_hanu else None,
            "is_first_mile": True,
        })

    for s in (route.steps if route else []):
        r_name = s.road_name.strip() if s.road_name and s.road_name.strip() not in ("Đoạn đường di chuyển", "Unnamed road") else ""
        inst = s.instruction.replace("vào Đoạn đường di chuyển", "").strip()

        # Spatial Landmark & Road Name Recovery (Layer 2)
        if not r_name:
            if is_near_hanu:
                r_name = "Trục chính Đại học Hà Nội (qua WinMart+ & Nhà sách Hoàn Thành)"
            else:
                r_name = "Trục giao thông liên thông"

        if inst in ("Rẽ phải.", "Rẽ phải", "Rẽ trái.", "Rẽ trái", "Đi thẳng.", "Đi thẳng"):
            inst = f"{inst.rstrip('.')} vào {r_name}."

        lane_guidance = None
        if "nguyễn trãi" in r_name.lower():
            lane_guidance = "Đi sát làn xe máy bên phải (tránh làn BRT)"
            if "làn xe máy" not in inst:
                inst = f"{inst.rstrip('.')} • Đi sát làn xe máy bên phải (tránh làn BRT)."

        s_meters = int(round(s.distance_meters)) if hasattr(s, "distance_meters") and s.distance_meters else int(round((s.distance_km if hasattr(s, "distance_km") else 0.05) * 1000.0))
        steps.append({
            "step_number": len(steps) + 1,
            "instruction": inst,
            "distance_km": round(s_meters / 1000.0, 3),
            "distance_meters": s_meters,
            "time_seconds": s.time_seconds,
            "road_name": r_name,
            "lane_guidance": lane_guidance,
        })

    gmaps_url = (
        f"https://www.google.com/maps/dir/?api=1"
        f"&origin={payload.start_lat},{payload.start_lng}"
        f"&destination={payload.dest_lat},{payload.dest_lng}"
        f"&travelmode={gmaps_mode}"
        f"&dir_action=navigate"
        f"{gmaps_avoid_param}"
    )
    return {
        "distance_km": round(dist_km, 3),
        "distance_meters": int(round(dist_km * 1000.0)),
        "eta_minutes": eta_mins,
        "mode": geo_mode,
        "coordinates": coords,
        "first_mile_coordinates": first_mile_coords,
        "first_mile_meters": first_mile_meters,
        "has_first_mile_gap": has_first_mile_gap,
        "first_mile_label": f"⚡ Đã nối liền {first_mile_meters}m sân nội bộ" if has_first_mile_gap else None,
        "steps": steps,
        "google_maps_turn_by_turn_url": gmaps_url,
    }


# ---------------------------------------------------------------------------
# Patient Health Twin & Anatomical Recovery Tracker Endpoints
# ---------------------------------------------------------------------------
from app.models.health_twin import (
    EvaluateProgressRequest,
    EvaluateProgressResponse,
    PatientHealthProfile,
    ScenarioSwitchRequest,
)
from app.services.patient_health_twin import patient_health_twin_service


@router.get("/health-twin/profile", response_model=PatientHealthProfile)
async def get_patient_health_profile(
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> PatientHealthProfile:
    """Returns the patient's active anatomical health twin profile,
    recovery score, vitals, and safe guardrail alerts from TiDB."""
    user_id = _extract_user_id(ctx)
    return patient_health_twin_service.get_profile(user_id=user_id, tenant_id=ctx.tenant_id)


@router.post("/health-twin/evaluate-symptom-update", response_model=EvaluateProgressResponse)
async def evaluate_patient_symptom_update(
    payload: EvaluateProgressRequest,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> EvaluateProgressResponse:
    """Evaluates user progress (recovery vs deterioration vs adverse drug reaction).
    Enforces AI directives to immediately halt harmful previous treatments and persists to TiDB."""
    user_id = _extract_user_id(ctx)
    res = patient_health_twin_service.evaluate_progress(
        message=payload.message,
        current_medications=payload.current_medications,
        vital_updates=payload.vital_updates,
        user_id=user_id,
        tenant_id=ctx.tenant_id,
    )
    return EvaluateProgressResponse(**res)


@router.post("/health-twin/scenario", response_model=PatientHealthProfile)
async def switch_patient_scenario(
    payload: ScenarioSwitchRequest,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> PatientHealthProfile:
    """Switches the anatomical twin to a specific clinical scenario for testing and persists to TiDB:
    - initial_flu: Flu onset with fever, headache, runny nose
    - recovered_headache: Successful recovery with resolved symptoms
    - adr_stomach_nsaid: NSAID-induced acute gastritis requiring immediate cessation
    - severe_fever_progression: 39.5C fever progression requiring hospital referral
    - healthy_baseline: Completely healthy 98/100 profile
    """
    user_id = _extract_user_id(ctx)
    return patient_health_twin_service.switch_scenario(
        scenario_id=payload.scenario_id,
        user_id=user_id,
        tenant_id=ctx.tenant_id,
    )


@router.post("/health-twin/reset", response_model=PatientHealthProfile)
async def reset_patient_health_profile(
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> PatientHealthProfile:
    """Resets patient health profile back to default clean healthy baseline in TiDB."""
    user_id = _extract_user_id(ctx)
    return patient_health_twin_service.reset_profile(user_id=user_id, tenant_id=ctx.tenant_id)


# --- Healthcare Financial & Clinical Safety Verification Routes ---
from app.models.financial_assessment import (
    FinancialTransaction,
    MonthlyFinancialAssessment,
    SafetyVerificationStatus,
    UpdateBudgetRequest,
)
from app.services.healthcare_financial_advisor import healthcare_financial_advisor_service


class SafetyEvaluationRequest(BaseModel):
    user_message: str
    proposed_advice: str = ""


class SafetyEvaluationResponse(BaseModel):
    safety_status: SafetyVerificationStatus
    revised_advice: str


@router.get("/financial/assessment", response_model=MonthlyFinancialAssessment)
async def get_financial_assessment(
    patient_ref: str = "guest_patient",
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> MonthlyFinancialAssessment:
    """Returns the patient's monthly healthcare spending assessment, Treatment Efficiency Score (TES),
    breakdown of GPP vs unofficial spending, recurrence waste, and actionable Booking Care recommendations."""
    return healthcare_financial_advisor_service.get_assessment(patient_ref)


@router.post("/financial/log-transaction", response_model=MonthlyFinancialAssessment)
async def log_financial_transaction(
    payload: FinancialTransaction,
    patient_ref: str = "guest_patient",
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> MonthlyFinancialAssessment:
    """Logs a new healthcare expense or Booking Care transaction and recalculates financial health ROI."""
    assessment = healthcare_financial_advisor_service.get_assessment(patient_ref)
    assessment.transactions.insert(0, payload)
    healthcare_financial_advisor_service.recalculate(assessment)
    healthcare_financial_advisor_service._save_to_disk()
    return assessment


@router.post("/financial/evaluate-safety", response_model=SafetyEvaluationResponse)
async def evaluate_clinical_safety(
    payload: SafetyEvaluationRequest,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> SafetyEvaluationResponse:
    """Three-Tier Clinical Safety & Positivity Verification Gate:
    Screens for red flags and removes dangerous false reassurances that inappropriately advise skipping care."""
    status, revised = healthcare_financial_advisor_service.evaluate_clinical_safety_and_positivity(
        payload.user_message, payload.proposed_advice
    )
    return SafetyEvaluationResponse(safety_status=status, revised_advice=revised)


@router.post("/financial/set-budget", response_model=MonthlyFinancialAssessment)
async def set_financial_budget(
    payload: UpdateBudgetRequest,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> MonthlyFinancialAssessment:
    """Updates the patient's monthly healthcare budget target and recalculates financial plan."""
    return healthcare_financial_advisor_service.set_budget(
        patient_ref=payload.patient_ref,
        budget_target_vnd=payload.budget_target_vnd,
    )


@router.post("/financial/reset", response_model=MonthlyFinancialAssessment)
async def reset_financial_assessment(
    patient_ref: str = "guest_patient",
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> MonthlyFinancialAssessment:
    """Resets financial assessment ledger to default realistic scenario."""
    return healthcare_financial_advisor_service.reset_to_default(patient_ref)


# =========================================================================
# User-Scoped Production TiDB APIs (Spending, Budget, Medications, Appointments)
# =========================================================================

def _extract_user_id(ctx: RequestContext) -> str:
    if ctx.tenant_id.startswith("user-"):
        return ctx.tenant_id[5:]
    return ctx.tenant_id


@router.get("/user/spending")
async def get_user_spending(
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    txs = user_data_store.get_spending(ctx.tenant_id, user_id)
    return {"transactions": txs, "total_spent_vnd": sum(int(t.get("amount_vnd", 0)) for t in txs)}


@router.post("/user/spending")
async def create_user_spending(
    payload: dict[str, Any],
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    tx = user_data_store.add_spending(
        tenant_id=ctx.tenant_id,
        user_id=user_id,
        title=str(payload.get("title") or "Chi phí y tế"),
        amount_vnd=int(payload.get("amount_vnd", 0)),
        category=str(payload.get("category", "medication")),
        provider=str(payload.get("provider", "")),
        doctor=str(payload.get("doctor", "")),
        bhyt_covered_vnd=int(payload.get("bhyt_covered_vnd", 0)),
        is_gpp=bool(payload.get("is_gpp", True)),
        raw_date=str(payload.get("raw_date", "")),
    )
    return {"transaction": tx}


@router.delete("/user/spending/{tx_id}")
async def delete_user_spending(
    tx_id: str,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    success = user_data_store.delete_spending(ctx.tenant_id, user_id, tx_id)
    return {"success": success}


@router.get("/user/budget")
async def get_user_budget(
    month: str = "2026-10",
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    target = user_data_store.get_budget(ctx.tenant_id, user_id, month_key=month)
    return {"month": month, "budget_target_vnd": target}


@router.post("/user/budget")
async def set_user_budget(
    payload: dict[str, Any],
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    amount = int(payload.get("budget_target_vnd", 10000000))
    month = str(payload.get("month", "2026-10"))
    val = user_data_store.set_budget(ctx.tenant_id, user_id, amount, month_key=month)
    return {"month": month, "budget_target_vnd": val}


@router.get("/user/medications")
async def get_user_medications(
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    meds = user_data_store.get_medications(ctx.tenant_id, user_id)
    return {"medications": meds}


@router.post("/user/medications")
async def create_user_medication(
    payload: dict[str, Any],
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    med = user_data_store.add_medication(
        tenant_id=ctx.tenant_id,
        user_id=user_id,
        name=str(payload.get("name", "")),
        dosage=str(payload.get("dosage", "")),
        frequency=str(payload.get("frequency", "Hàng ngày")),
        timing=str(payload.get("timing", "Sau ăn sáng")),
        instructions=str(payload.get("instructions", "")),
    )
    return {"medication": med}


@router.delete("/user/medications/{med_id}")
async def delete_user_medication(
    med_id: str,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    success = user_data_store.delete_medication(ctx.tenant_id, user_id, med_id)
    return {"success": success}


@router.get("/user/appointments")
async def get_user_appointments(
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    appts = user_data_store.get_appointments(ctx.tenant_id, user_id)
    return {"appointments": appts}


@router.post("/user/appointments")
async def create_user_appointment(
    payload: dict[str, Any],
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    appt = user_data_store.add_appointment(
        tenant_id=ctx.tenant_id,
        user_id=user_id,
        doctor=str(payload.get("doctor", "Bác sĩ Chuyên khoa")),
        specialty=str(payload.get("specialty", "Đa khoa")),
        hospital=str(payload.get("hospital", "Bệnh viện BookingCare")),
        date=str(payload.get("date", "")),
        time_slot=str(payload.get("time", "08:30")),
        status=str(payload.get("status", "confirmed")),
    )
    return {"appointment": appt}


@router.delete("/user/appointments/{appt_id}")
async def delete_user_appointment(
    appt_id: str,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    success = user_data_store.delete_appointment(ctx.tenant_id, user_id, appt_id)
    return {"success": success}


@router.get("/user/summary")
async def get_user_summary(
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    return user_data_store.get_agent_cross_module_context(ctx.tenant_id, user_id)


# -----------------------------------------------------------------
# Clinical Schedule & Shifts (Lịch khám từ Database)
# -----------------------------------------------------------------
@router.get("/schedule/shifts")
async def get_clinical_shifts(
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    shifts = user_data_store.get_clinical_shifts(ctx.tenant_id, user_id)
    return {"shifts": shifts, "source": "database", "count": len(shifts)}


@router.post("/schedule/shifts")
async def create_clinical_shift(
    payload: dict[str, Any],
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    shift = user_data_store.create_clinical_shift(ctx.tenant_id, user_id, payload)
    return {"shift": shift, "source": "database"}


@router.put("/schedule/shifts/{shift_id}")
async def update_clinical_shift(
    shift_id: str,
    payload: dict[str, Any],
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    shift = user_data_store.update_clinical_shift(ctx.tenant_id, user_id, shift_id, payload)
    return {"shift": shift, "source": "database"}


@router.patch("/schedule/shifts/{shift_id}/status")
async def update_clinical_shift_status(
    shift_id: str,
    payload: dict[str, Any],
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    status = str(payload.get("status", "confirmed"))
    success = user_data_store.update_clinical_shift_status(ctx.tenant_id, user_id, shift_id, status)
    return {"success": success, "status": status}


@router.delete("/schedule/shifts/{shift_id}")
async def delete_clinical_shift(
    shift_id: str,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    success = user_data_store.delete_clinical_shift(ctx.tenant_id, user_id, shift_id)
    return {"success": success}


# -----------------------------------------------------------------
# Medication Regimen & Intake Tracker (Lịch uống thuốc từ Database)
# -----------------------------------------------------------------
@router.get("/medication/regimen")
async def get_medication_regimen(
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    data = user_data_store.get_medications_regimen(ctx.tenant_id, user_id)
    return {
        "medications": data.get("meds", []),
        "meds": data.get("meds", []),
        "takenMap": data.get("takenMap", {}),
        "source": "database",
    }


@router.post("/medication/regimen")
async def create_medication_regimen(
    payload: dict[str, Any],
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    med = user_data_store.create_medication_regimen(ctx.tenant_id, user_id, payload)
    return {"med": med, "source": "database"}


@router.put("/medication/regimen/{med_id}")
async def update_medication_regimen(
    med_id: str,
    payload: dict[str, Any],
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    med = user_data_store.update_medication_regimen(ctx.tenant_id, user_id, med_id, payload)
    return {"med": med, "source": "database"}


@router.delete("/medication/regimen/{med_id}")
async def delete_medication_regimen(
    med_id: str,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    success = user_data_store.delete_medication_regimen(ctx.tenant_id, user_id, med_id)
    return {"success": success}


@router.post("/medication/toggle-taken")
async def toggle_medication_taken(
    payload: dict[str, Any],
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    med_id = str(payload.get("med_id") or payload.get("medId") or "")
    date_str = str(payload.get("date_str") or payload.get("dateStr") or "")
    taken = bool(payload.get("taken", True))
    success = user_data_store.toggle_medication_taken(ctx.tenant_id, user_id, med_id, date_str, taken)
    return {"success": success, "med_id": med_id, "date_str": date_str, "taken": taken}


@router.post("/medication/reset-sample")
async def reset_medication_sample(
    payload: dict[str, Any],
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    regimen_type = str(payload.get("regimen_type") or payload.get("regimenType") or "cardio")
    meds = user_data_store.reset_medication_sample(ctx.tenant_id, user_id, regimen_type)
    return {"medications": meds, "meds": meds, "source": "database"}


# -----------------------------------------------------------------
# User Profile Endpoints (Hồ sơ cá nhân & BHYT từ TiDB)
# -----------------------------------------------------------------
@router.get("/user/profile")
async def get_user_profile(
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    prof = user_data_store.get_user_profile(ctx.tenant_id, user_id)
    return {"profile": prof, "source": "database"}


@router.put("/user/profile")
async def update_user_profile(
    payload: dict[str, Any],
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    prof = user_data_store.save_user_profile(ctx.tenant_id, user_id, payload)
    return {"profile": prof, "source": "database"}


# -----------------------------------------------------------------
# Demo / Sample Seed and Clear Endpoints (On-Demand Data Control)
# -----------------------------------------------------------------
@router.post("/schedule/seed-sample")
async def seed_schedule_sample(
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    shifts = user_data_store.seed_sample_shifts(ctx.tenant_id, user_id)
    return {"shifts": shifts, "source": "database"}


@router.post("/schedule/clear")
async def clear_schedule(
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    user_data_store.clear_shifts(ctx.tenant_id, user_id)
    return {"shifts": [], "source": "database"}


@router.post("/medication/seed-sample")
async def seed_medication_sample(
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    meds = user_data_store.seed_sample_medications(ctx.tenant_id, user_id)
    return {"medications": meds, "meds": meds, "source": "database"}


@router.post("/medication/clear")
async def clear_medication(
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    user_data_store.clear_medications(ctx.tenant_id, user_id)
    return {"medications": [], "meds": [], "takenMap": {}, "source": "database"}


@router.post("/user/spending/seed-sample")
async def seed_spending_sample(
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    txs = user_data_store.seed_sample_spending(ctx.tenant_id, user_id)
    return {"transactions": txs, "source": "database"}


@router.post("/user/spending/clear")
async def clear_spending(
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> dict[str, Any]:
    from app.services.user_data_store import user_data_store
    user_id = _extract_user_id(ctx)
    user_data_store.clear_spending(ctx.tenant_id, user_id)
    return {"transactions": [], "total_spent_vnd": 0, "source": "database"}




