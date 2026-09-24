"""Regression tests verifying bugfixes for vital_signs alias, prescription storage, and DB audit."""

import io
import pytest
from fastapi.testclient import TestClient

from app.core.database import db_manager
from app.core.storage import storage_manager
from app.main import app
from app.models.triage import TriageRequest, VitalSigns
from app.services.audit import AuditEvent, audit_store

client = TestClient(app)


def test_triage_request_accepts_both_vitals_and_vital_signs():
    # 1. Using 'vitals'
    req1 = TriageRequest(
        patient_ref="p-1",
        symptoms_text="đau đầu",
        vitals=VitalSigns(heart_rate=80, systolic=120, diastolic=80),
    )
    assert req1.vitals is not None
    assert req1.vitals.heart_rate == 80

    # 2. Using 'vital_signs' (from BookingCare client or external HIS)
    req2 = TriageRequest.model_validate({
        "patient_ref": "p-2",
        "symptoms_text": "đau đầu",
        "vital_signs": {"heart_rate": 88, "systolic": 130, "diastolic": 85},
    })
    assert req2.vitals is not None
    assert req2.vitals.heart_rate == 88


def test_prescription_extract_persists_image_to_storage():
    image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 40
    response = client.post(
        "/v1/prescription/extract",
        headers={"X-API-Key": "demo-key", "X-Tenant-Id": "tenant-demo", "Idempotency-Key": "storage-fix-1"},
        files={"image": ("prescription.png", io.BytesIO(image_bytes), "image/png")},
        data={"patient_ref": "p-storage-test"},
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    # Verify image is present in storage_manager
    stored = storage_manager.retrieve(tenant_id="tenant-demo", object_id=job_id)
    assert stored is not None
    retrieved_bytes, content_type = stored
    assert retrieved_bytes == image_bytes
    assert content_type == "image/png"


def test_audit_store_persists_to_database():
    event = AuditEvent(
        request_id="req_db_test_01",
        tenant_id="tenant-demo",
        action="clinical.audit.test",
        payload_type="TestPayload",
        metadata={"key": "value"},
    )
    audit_store.append(event)

    # Query from audit_store
    results = audit_store.query(tenant_id="tenant-demo", request_id="req_db_test_01")
    assert len(results) >= 1
    assert results[0].action == "clinical.audit.test"

    # Query directly from database session to ensure DB persistence
    with db_manager.tenant_context("tenant-demo") as session:
        rows = session.execute("SELECT * FROM audit_events WHERE request_id = ?", ("req_db_test_01",))
        assert len(rows) >= 1
        assert rows[0]["action"] == "clinical.audit.test"
