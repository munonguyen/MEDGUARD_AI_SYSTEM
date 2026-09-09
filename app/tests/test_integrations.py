"""Integration tests for FHIR R4, Consent Gating, Prometheus Metrics, and Infrastructure."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.queue import job_queue
from app.core.secrets import secret_manager
from app.core.storage import storage_manager
from app.main import app

client = TestClient(app)


def auth_headers(idempotency_key: str = "integ-key-1") -> dict[str, str]:
    return {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "Idempotency-Key": idempotency_key,
    }


def test_fhir_export_bundle():
    response = client.post(
        "/v1/fhir/export",
        headers=auth_headers("fhir-export-1"),
        json={
            "patient_ref": "p-fhir-001",
            "medications": [
                {
                    "name": "Augmentin 1g",
                    "active_ingredient": "amoxicillin",
                    "strength": "1g",
                    "instructions": "Take 1 tablet twice daily",
                }
            ],
            "observations": [
                {
                    "indicator": "heart_rate",
                    "value": 78.0,
                    "unit": "bpm",
                }
            ],
            "triage": {
                "esi_level": 3,
                "urgency": "URGENT",
                "red_flags": ["Fever above 38.5"],
                "specialty": "INTERNAL_MEDICINE",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["resourceType"] == "Bundle"
    assert data["type"] == "collection"
    assert data["total"] == 3

    resource_types = [entry["resource"]["resourceType"] for entry in data["entry"]]
    assert "MedicationRequest" in resource_types
    assert "Observation" in resource_types
    assert "RiskAssessment" in resource_types

    # Verify intent is proposal for AI medication request
    mr = next(e["resource"] for e in data["entry"] if e["resource"]["resourceType"] == "MedicationRequest")
    assert mr["intent"] == "proposal"
    assert mr["subject"]["reference"] == "Patient/p-fhir-001"


def test_consent_revocation_rejected():
    headers = auth_headers("consent-revoked-1")
    headers["X-Consent-Token"] = "revoked"

    response = client.post(
        "/v1/triage",
        headers=headers,
        json={"patient_ref": "p-consent", "symptoms_text": "đau đầu nhẹ"},
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "consent_revoked"


def test_prometheus_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    text = response.text
    assert "medguard_requests_total" in text
    assert "# HELP" in text
    assert "# TYPE" in text


def test_secret_manager_key_rotation():
    # Initial key works
    assert secret_manager.verify_key(tenant_id="tenant-demo", raw_key="demo-key") is True
    assert secret_manager.verify_key(tenant_id="tenant-demo", raw_key="wrong-key") is False

    # Rotate to new key
    secret_manager.rotate_key(tenant_id="tenant-demo", new_raw_key="new-demo-key-2026")

    # Both old (rotating) and new (active) work during transition
    assert secret_manager.verify_key(tenant_id="tenant-demo", raw_key="new-demo-key-2026") is True
    assert secret_manager.verify_key(tenant_id="tenant-demo", raw_key="demo-key") is True


def test_storage_manager_lifecycle():
    tenant = "tenant-test"
    obj_id = "test-obj-123"
    payload = b"Prescription secret image data"

    # Store
    storage_manager.store(
        tenant_id=tenant,
        object_id=obj_id,
        data=payload,
        content_type="image/png",
        ttl_seconds=3600,
    )

    # Retrieve
    retrieved = storage_manager.retrieve(tenant_id=tenant, object_id=obj_id)
    assert retrieved is not None
    data, content_type = retrieved
    assert data == payload
    assert content_type == "image/png"

    # Delete
    assert storage_manager.delete(tenant_id=tenant, object_id=obj_id) is True
    assert storage_manager.retrieve(tenant_id=tenant, object_id=obj_id) is None


def test_queue_manager_lifecycle():
    tenant = "tenant-test"
    job_id = "job-queue-123"

    job_queue.enqueue(
        tenant_id=tenant,
        job_id=job_id,
        payload={"action": "extract_prescription"},
        priority=5,
    )
    assert job_queue.queue_depth(tenant) >= 1

    msg = job_queue.dequeue()
    assert msg is not None
    assert msg.job_id == job_id
    assert msg.tenant_id == tenant

    job_queue.ack(job_id)
