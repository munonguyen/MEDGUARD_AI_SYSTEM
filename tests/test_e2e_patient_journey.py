"""Comprehensive End-to-End (E2E) Patient Clinical Journey Integration Test.

Simulates the complete patient workflow connecting BookingCare and MedGuard AI:
  Step 1: Patient Symptom Intake -> /v1/triage (Emergency detection & Specialty Routing)
  Step 2: Emergency vs Urgent/Routine Routing -> /v1/queue/prioritize
  Step 3: Post-consultation Prescription Upload -> /v1/prescription/extract
  Step 4: Fail-Closed Prescription OCR Job Polling -> /v1/jobs/{job_id}
  Step 5: Medication Safety Analysis -> /v1/medication/safety-check (Drug-Drug & Allergies)
  Step 6: Medication Adherence Schedule Generation -> /v1/medication/schedules
  Step 7: Post-discharge Follow-up Care Plan -> /v1/followup/plan
"""

from __future__ import annotations

from datetime import datetime, timezone, date
import io
from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)

HEADERS = {
    "X-API-Key": "demo-key",
    "X-Tenant-Id": "tenant-demo",
}


def test_complete_e2e_patient_clinical_journey():
    # -------------------------------------------------------------------------
    # STEP 1: Patient Intake & Clinical Triage (Cardiac Symptom)
    # -------------------------------------------------------------------------
    triage_req = {
        "patient_ref": "patient-bc-0922",
        "symptoms_text": "Đau tức ngực dữ dội lan lên cổ kèm khó thở và vã mồ hôi lạnh.",
        "vital_signs": {
            "heart_rate": 115,
            "spo2": 94,
            "systolic": 155,
            "diastolic": 95,
        },
        "locale": "vi-VN",
    }
    resp = client.post(
        "/v1/triage",
        json=triage_req,
        headers={**HEADERS, "Idempotency-Key": "e2e-step1-triage-001"},
    )
    assert resp.status_code == 200, resp.text
    triage_data = resp.json()

    assert triage_data["urgency"] == "EMERGENCY"
    assert triage_data["emergency_flag"] is True
    assert triage_data["recommended_specialty"] is not None
    assert triage_data["recommended_specialty"]["label"] == "Tim mạch"
    assert len(triage_data["red_flags"]) > 0
    assert "115" in triage_data["advice"]
    print("\n[E2E Step 1 PASS] Triage identified EMERGENCY -> Tim mạch, 115 alert.")

    # -------------------------------------------------------------------------
    # STEP 2: Queue Prioritization
    # -------------------------------------------------------------------------
    queue_req = {
        "items": [
            {
                "patient_ref": "patient-routine-01",
                "urgency": "ROUTINE",
                "wait_minutes": 25,
                "emergency_flag": False,
            },
            {
                "patient_ref": "patient-bc-0922",
                "urgency": "EMERGENCY",
                "wait_minutes": 5,
                "emergency_flag": True,
            },
        ],
        "locale": "vi-VN",
    }
    resp_queue = client.post(
        "/v1/queue/prioritize",
        json=queue_req,
        headers={**HEADERS, "Idempotency-Key": "e2e-step2-queue-001"},
    )
    assert resp_queue.status_code == 200, resp_queue.text
    prioritized = resp_queue.json()["items"]
    assert prioritized[0]["patient_ref"] == "patient-bc-0922"
    assert prioritized[0]["rank"] == 1
    assert prioritized[0]["priority_band"] == "EMERGENCY"
    print("[E2E Step 2 PASS] Emergency patient prioritized to Rank 1.")

    # -------------------------------------------------------------------------
    # STEP 3: Prescription Upload & Asynchronous OCR Extraction
    # -------------------------------------------------------------------------
    fake_prescription_img = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB\x00C\x00" + (b"\x00" * 200)
    files = {"image": ("prescription_scan.jpg", io.BytesIO(fake_prescription_img), "image/jpeg")}
    data = {"patient_ref": "patient-bc-0922"}

    resp_ocr = client.post(
        "/v1/prescription/extract",
        data=data,
        files=files,
        headers={
            **HEADERS,
            "Idempotency-Key": "e2e-step3-ocr-001",
            "X-Consent-Token": "consent-valid-proof-001",
        },
    )
    assert resp_ocr.status_code == 202, resp_ocr.text
    ocr_job = resp_ocr.json()
    job_id = ocr_job["job_id"]
    assert job_id is not None
    assert ocr_job["status"] in ("queued", "pending", "processing", "pending_review")
    print(f"[E2E Step 3 PASS] Prescription accepted for processing with Job ID: {job_id}")

    # -------------------------------------------------------------------------
    # STEP 4: Fail-Closed Job Polling
    # -------------------------------------------------------------------------
    resp_job = client.get(f"/v1/jobs/{job_id}", headers=HEADERS)
    assert resp_job.status_code == 200
    job_status = resp_job.json()
    assert job_status["status"] in ("queued", "pending", "failed", "pending_review")
    print(f"[E2E Step 4 PASS] OCR Job Polling verified with fail-closed status: {job_status['status']}.")

    # -------------------------------------------------------------------------
    # STEP 5: Medication Safety & Interaction Check (Aspirin + Warfarin)
    # -------------------------------------------------------------------------
    safety_req = {
        "patient_ref": "patient-bc-0922",
        "current_medications": [
            {"name": "Warfarin", "active_ingredient": "warfarin"}
        ],
        "proposed_medications": [
            {"name": "Aspirin", "active_ingredient": "aspirin"}
        ],
        "allergies": [{"substance": "penicillin", "severity": "HIGH"}],
        "conditions": ["loét dạ dày"],
    }
    resp_safety = client.post(
        "/v1/medication/safety-check",
        json=safety_req,
        headers={**HEADERS, "Idempotency-Key": "e2e-step5-safety-001"},
    )
    assert resp_safety.status_code == 200
    safety_data = resp_safety.json()

    assert safety_data["overall_risk"] in ("MODERATE", "HIGH")
    assert safety_data["requires_human_review"] is True
    assert len(safety_data["warnings"]) > 0
    assert any(w["type"] == "DRUG_DRUG_INTERACTION" for w in safety_data["warnings"])
    print("[E2E Step 5 PASS] Medication Safety identified Warfarin + Aspirin interaction.")

    # -------------------------------------------------------------------------
    # STEP 6: Approved Medication Schedule Generation
    # -------------------------------------------------------------------------
    schedule_req = {
        "patient_ref": "patient-bc-0922",
        "medication_name": "Clopidogrel 75mg",
        "dosage_text": "1 viên sau ăn sáng",
        "scheduled_at": datetime.now(timezone.utc).isoformat(),
        "recurrence": "daily",
        "source": "prescription_review",
    }
    resp_sched = client.post(
        "/v1/medication-schedules",
        json=schedule_req,
        headers={**HEADERS, "Idempotency-Key": "e2e-step6-sched-001"},
    )
    assert resp_sched.status_code == 201, resp_sched.text
    sched_data = resp_sched.json()
    assert sched_data["medication_name"] == "Clopidogrel 75mg"
    assert sched_data["patient_ref"] == "patient-bc-0922"

    # Query schedules
    resp_get_sched = client.get(
        "/v1/medication-schedules?patient_ref=patient-bc-0922",
        headers=HEADERS,
    )
    assert resp_get_sched.status_code == 200
    assert len(resp_get_sched.json()["schedules"]) >= 1
    print("[E2E Step 6 PASS] Medication schedule created and verified.")

    # -------------------------------------------------------------------------
    # STEP 7: Post-discharge Follow-Up Care Plan
    # -------------------------------------------------------------------------
    followup_req = {
        "patient_ref": "patient-bc-0922",
        "diagnosis_text": "Hội chứng vành cấp đã can thiệp ổn định",
        "discharge_date": date.today().isoformat(),
        "conditions": ["tăng huyết áp", "bệnh mạch vành"],
    }
    resp_followup = client.post(
        "/v1/followup/plan",
        json=followup_req,
        headers={**HEADERS, "Idempotency-Key": "e2e-step7-followup-001"},
    )
    assert resp_followup.status_code == 200, resp_followup.text
    plan = resp_followup.json()
    assert plan["plan_available"] is True
    assert len(plan["suggestions"]) > 0
    print(f"[E2E Step 7 PASS] Follow-up care plan generated: {len(plan['suggestions'])} suggestions.")
    print("\n>>> ALL 7 E2E PATIENT CLINICAL JOURNEY STEPS PASSED SUCCESSFULLY! <<<\n")
