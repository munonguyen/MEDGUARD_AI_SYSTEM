"""4-Stage Prescription Vision OCR Worker.

Orchestrates:
- Stage 1: Preprocessing & Bounding Box Detection (PaddleOCR)
- Stage 2: Vietnamese Line Recognition (VietOCR)
- Stage 3: Structured Clinical Entity Normalization (Vintern-1B / VLM)
- Stage 4: Fail-Closed Catalog Matching (Similarity >= 0.85, null on mismatch)

Always enforces review_status = 'PENDING_REVIEW' and appends audit events.
"""

from __future__ import annotations

from time import time
from typing import Any

from app.core.config import settings
from app.core.observability import metrics
from app.core.queue import job_queue
from app.core.storage import storage_manager
from app.services.audit import AuditEvent, audit_store
from app.services.jobs import job_store
from app.services.ocr.detector import text_detector
from app.services.ocr.errors import OcrPipelineError, ocr_error_code
from app.services.ocr.extractor import entity_extractor
from app.services.ocr.matcher import match_medication_to_catalog
from app.services.ocr.preprocessor import preprocess_prescription_image
from app.services.ocr.recognizer import line_recognizer


def run_vision_pipeline(image_bytes: bytes) -> dict[str, Any]:
    """Executes all 4 stages of the vision pipeline synchronously on image bytes."""
    # Stage 1a: Preprocessing
    preprocessed = preprocess_prescription_image(image_bytes)
    if not preprocessed.is_valid:
        raise OcrPipelineError(preprocessed.error_message or "invalid_image")

    if not text_detector.is_real_engine_available or not line_recognizer.is_real_engine_available:
        raise OcrPipelineError("ocr_worker_unavailable")

    # Stage 1b: Region Detection
    boxes = text_detector.detect_boxes(image_bytes)
    if not boxes:
        raise OcrPipelineError("ocr_no_text_detected")

    # Stage 2: Line Recognition
    lines = line_recognizer.recognize_lines(image_bytes, boxes)
    if not lines:
        raise OcrPipelineError("ocr_no_text_recognized")

    # Stage 3: Structured Entity Extraction
    extracted_meds = entity_extractor.extract_medications(image_bytes, lines)
    if not extracted_meds:
        raise OcrPipelineError("ocr_no_medications_detected")

    # Stage 4: Fail-Closed Catalog Matching
    matched_meds: list[dict[str, Any]] = []
    has_unmatched = False

    for med in extracted_meds:
        match_result = match_medication_to_catalog(
            extracted_name=med.medicine_name,
            extracted_strength=med.strength,
            threshold=settings.prescription_match_threshold,
        )
        if match_result["matched_product"] is None:
            has_unmatched = True

        matched_meds.append({
            "raw_text": med.raw_text,
            "extracted_entity": {
                "medicine_name": med.medicine_name,
                "active_ingredient": med.active_ingredient,
                "strength": med.strength,
                "dosage_form": med.dosage_form,
                "route": med.route,
                "frequency": med.frequency,
                "duration_days": med.duration_days,
                "instructions": med.instructions,
            },
            "catalog_match": match_result,
            "confidence": med.overall_confidence,
            "field_confidences": med.field_confidences,
        })

    avg_confidence = sum(m["confidence"] for m in matched_meds) / len(matched_meds)

    return {
        "pipeline_version": "v1-4stage-paddle-vietocr-vintern",
        "stages_executed": [
            "stage_1_preprocessing_and_detection",
            "stage_2_vietnamese_line_ocr",
            "stage_3_vlm_entity_normalization",
            "stage_4_fail_closed_catalog_matching",
        ],
        "quality_metrics": {
            "width": preprocessed.width,
            "height": preprocessed.height,
            "blur_score": preprocessed.blur_score,
            "total_boxes_detected": len(boxes),
            "total_lines_recognized": len(lines),
            "average_confidence": round(avg_confidence, 3),
        },
        "extracted_medications": matched_meds,
        "review_status": "PENDING_REVIEW",
        "requires_human_pharmacist_review": True,
        "has_unmatched_items": has_unmatched,
        "disclaimer": "Kết quả bóc tách đơn thuốc bằng AI nhằm mục đích hỗ trợ tra cứu. Dược sĩ/Bác sĩ có thẩm quyền bắt buộc phải thẩm định và xác nhận trước khi cấp phát thuốc.",
    }


def process_next_ocr_job(timeout_seconds: float = 0.5) -> str | None:
    """Claims one job and processes it through the 4-stage pipeline."""
    while True:
        message = job_queue.dequeue(timeout_seconds)
        if message is None:
            return None
        job = job_store.get_for_worker(message.tenant_id, message.job_id)
        if job is None:
            job_queue.fail(message.job_id, "job_not_found", requeue=False)
            continue
        recovered_claim = job.status == "processing" and message.attempts > 1
        if job.status == "queued":
            if job_store.mark_processing(job):
                break
            job_queue.ack(job.job_id)
            continue
        if not recovered_claim:
            job_queue.ack(job.job_id)
            continue
        break

    try:
        stored = storage_manager.retrieve(tenant_id=job.tenant_id, object_id=job.job_id)
        if stored is None:
            raise OcrPipelineError("ocr_source_object_missing")
        image_bytes = stored[0]

        result = run_vision_pipeline(image_bytes)
        job_store.complete(job, result)

        audit_store.append(
            AuditEvent(
                request_id=job.request_id,
                tenant_id=job.tenant_id,
                action="prescription.ocr.completed",
                payload_type="PrescriptionJob",
                metadata={
                    "job_id": job.job_id,
                    "review_status": "PENDING_REVIEW",
                    "items_count": len(result["extracted_medications"]),
                    "has_unmatched": result["has_unmatched_items"],
                },
            )
        )
        metrics.inc_counter(
            "medguard_ocr_jobs_completed_total",
            labels={"tenant_id": job.tenant_id, "status": "completed"},
        )
        job_queue.ack(job.job_id)
        return job.job_id

    except Exception as exc:
        error_code = ocr_error_code(exc)
        job_store.fail(job, error_code)
        audit_store.append(
            AuditEvent(
                request_id=job.request_id,
                tenant_id=job.tenant_id,
                action="prescription.ocr.failed",
                payload_type="PrescriptionJob",
                metadata={"job_id": job.job_id, "error_code": error_code},
            )
        )
        metrics.inc_counter(
            "medguard_ocr_jobs_completed_total",
            labels={"tenant_id": job.tenant_id, "status": "failed"},
        )
        job_queue.fail(job.job_id, error_code, requeue=False)
        return job.job_id
