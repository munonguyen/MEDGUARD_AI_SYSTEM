from __future__ import annotations

import asyncio
from contextlib import suppress
from hashlib import sha256
from typing import Any

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
    response = orchestrate_chat(payload, ctx)
    store_idempotent_response(action="chat.respond", payload=payload, ctx=ctx, response=response)
    return response


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
