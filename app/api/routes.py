from __future__ import annotations

import asyncio
from contextlib import suppress
from hashlib import sha256
from typing import Any

from pydantic import BaseModel
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status

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


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    ctx: RequestContext = Depends(verify_tenant_api_key),
    consent_token: str = Depends(verify_patient_consent),
) -> ChatResponse:
    cached = get_idempotent_response(action="chat.respond", payload=payload, ctx=ctx)
    if cached:
        return ChatResponse.model_validate(cached)
    preparation, token = begin_voice(payload.voice.persona) if payload.voice else (None, None)
    try:
        response = orchestrate_chat(payload, ctx)
        if preparation is not None:
            response.spoken_reply = spoken_reply(response)
            prepared = preparation.approve(response, ctx.tenant_id)
            if prepared is not None:
                from app.models.chat import PreparedSpeech
                response.prepared_speech = PreparedSpeech(**prepared)
    finally:
        if preparation is not None:
            end_voice(preparation, token)
    # Short-lived speech capabilities must never be persisted with a response.
    persisted = response.model_copy(update={"prepared_speech": None})
    store_idempotent_response(action="chat.respond", payload=payload, ctx=ctx, response=persisted)
    return response


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
    limit: int = 50,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> ConversationListResponse:
    return ConversationListResponse(
        conversations=chat_history_store.list(ctx.tenant_id, limit=max(1, min(limit, 100)))
    )


@router.get("/chat/conversations/{conversation_id}", response_model=ConversationHistoryResponse)
def chat_conversation(
    conversation_id: str,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> ConversationHistoryResponse:
    conversation = chat_history_store.get(ctx.tenant_id, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "conversation_not_found", "message": "Conversation was not found."},
        )
    return conversation


@router.delete("/chat/conversations/{conversation_id}", status_code=204)
def delete_chat_conversation(
    conversation_id: str,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> None:
    if not chat_history_store.delete(ctx.tenant_id, conversation_id):
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
                "operating_status": {
                    "is_open": p.operating_status.is_open,
                    "status_badge": p.operating_status.status_badge,
                    "status_label": p.operating_status.status_label,
                    "detail_text": p.operating_status.detail_text,
                },
                "distance_km": dist_km,
                "google_maps_turn_by_turn_url": gmaps_url,
            })

    out.sort(key=lambda x: x["distance_km"])
    return {
        "city": city,
        "poi_type": poi_type,
        "user_coordinates": {"lat": user_lat, "lng": user_lng},
        "count": len(out),
        "pois": out,
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
    dist_km = route.distance_km if route else round(haversine * 1.3, 2)
    # Estimate ETA depending on travel mode
    if route:
        eta_mins = route.eta_minutes
    else:
        speed_factor = 2.0 if geo_mode == "motorcycle" else (2.5 if geo_mode == "drive" else 12.0)
        eta_mins = max(2, int(dist_km * speed_factor))

    steps = [
        {
            "step_number": s.step_number,
            "instruction": s.instruction,
            "distance_km": round(s.distance_meters / 1000.0, 2),
            "time_seconds": s.time_seconds,
            "road_name": s.road_name or "Đoạn đường di chuyển",
        }
        for s in (route.steps if route else [])
    ]
    coords = route.coordinates if route else [[payload.start_lat, payload.start_lng], [payload.dest_lat, payload.dest_lng]]
    gmaps_url = (
        f"https://www.google.com/maps/dir/?api=1"
        f"&origin={payload.start_lat},{payload.start_lng}"
        f"&destination={payload.dest_lat},{payload.dest_lng}"
        f"&travelmode={gmaps_mode}"
        f"&dir_action=navigate"
        f"{gmaps_avoid_param}"
    )
    return {
        "distance_km": dist_km,
        "eta_minutes": eta_mins,
        "mode": geo_mode,
        "coordinates": coords,
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
    recovery score, vitals, and safe guardrail alerts."""
    return patient_health_twin_service.get_profile()


@router.post("/health-twin/evaluate-symptom-update", response_model=EvaluateProgressResponse)
async def evaluate_patient_symptom_update(
    payload: EvaluateProgressRequest,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> EvaluateProgressResponse:
    """Evaluates user progress (recovery vs deterioration vs adverse drug reaction).
    Enforces AI directives to immediately halt harmful previous treatments."""
    res = patient_health_twin_service.evaluate_progress(
        message=payload.message,
        current_medications=payload.current_medications,
        vital_updates=payload.vital_updates,
    )
    return EvaluateProgressResponse(**res)


@router.post("/health-twin/scenario", response_model=PatientHealthProfile)
async def switch_patient_scenario(
    payload: ScenarioSwitchRequest,
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> PatientHealthProfile:
    """Switches the anatomical twin to a specific clinical scenario for testing:
    - initial_flu: Flu onset with fever, headache, runny nose
    - recovered_headache: Successful recovery with resolved symptoms
    - adr_stomach_nsaid: NSAID-induced acute gastritis requiring immediate cessation
    - severe_fever_progression: 39.5C fever progression requiring hospital referral
    - healthy_baseline: Completely healthy 98/100 profile
    """
    return patient_health_twin_service.switch_scenario(payload.scenario_id)


@router.post("/health-twin/reset", response_model=PatientHealthProfile)
async def reset_patient_health_profile(
    ctx: RequestContext = Depends(verify_tenant_credentials),
) -> PatientHealthProfile:
    """Resets patient health profile back to default initial flu episode."""
    return patient_health_twin_service.switch_scenario("initial_flu")

