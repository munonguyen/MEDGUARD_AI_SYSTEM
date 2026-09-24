"""Tests for Clinical Web UI Dashboard and Job Workflow Endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def auth_headers(tenant_id: str = "tenant-demo", key: str = "demo-key") -> dict[str, str]:
    return {
        "X-API-Key": key,
        "X-Tenant-Id": tenant_id,
        "Idempotency-Key": "test-idem-ui-001",
        "X-Consent-Token": "consent-valid-test",
    }


def test_dashboard_and_static_assets_serving():
    root_res = client.get("/")
    assert root_res.status_code == 200
    assert "text/html" in root_res.headers.get("content-type", "")
    assert "MedGuard AI" in root_res.text
    assert '<div id="root"></div>' in root_res.text
    assert 'src="/static/app.js"' in root_res.text

    dash_res = client.get("/dashboard")
    assert dash_res.status_code == 200
    assert "MedGuard AI" in dash_res.text

    css_res = client.get("/static/style.css")
    assert css_res.status_code == 200
    assert "css" in css_res.headers.get("content-type", "")
    assert "--sidebar" in css_res.text
    assert ".workspace" in css_res.text

    js_res = client.get("/static/app.js")
    assert js_res.status_code == 200
    assert "javascript" in js_res.headers.get("content-type", "")
    assert "createRoot" in js_res.text
    assert "Phân luồng triệu chứng" in js_res.text
    assert "Đọc đơn thuốc" in js_res.text
    assert "System & audit" in js_res.text


def test_prescription_job_processing_fails_closed_without_ocr_backend():
    # Upload a prescription to get a job_id
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00"
    )
    upload_res = client.post(
        "/v1/prescription/extract",
        headers={
            "X-API-Key": "demo-key",
            "X-Tenant-Id": "tenant-demo",
            "Idempotency-Key": "idem-extract-workflow-1",
            "X-Consent-Token": "consent-token-123",
        },
        files={"image": ("rx.png", png_bytes, "image/png")},
        data={"patient_ref": "BN-WORKFLOW-01"},
    )
    assert upload_res.status_code == 202
    job_id = upload_res.json()["job_id"]

    # Trigger OCR processing on this job
    process_res = client.post(
        f"/v1/jobs/{job_id}/process",
        headers={
            "X-API-Key": "demo-key",
            "X-Tenant-Id": "tenant-demo",
            "Idempotency-Key": "process-workflow-1",
        },
    )
    assert process_res.status_code == 200
    job_data = process_res.json()
    assert job_data["status"] == "failed"
    assert job_data["review_status"] == "FAILED"
    assert job_data["result"] is None
    assert job_data["error_code"] == "ocr_worker_unavailable"

    # Pharmacist reviews and approves the job
    review_res = client.post(
        f"/v1/jobs/{job_id}/review?approved=true",
        headers={
            "X-API-Key": "demo-key",
            "X-Tenant-Id": "tenant-demo",
            "Idempotency-Key": "review-workflow-1",
        },
    )
    assert review_res.status_code == 409
    assert review_res.json()["error_code"] == "job_not_reviewable"


def test_audit_events_endpoint_with_tenant_isolation():
    # Read audit events for tenant-demo
    res_demo = client.get(
        "/v1/audit/events?limit=10",
        headers={"X-API-Key": "demo-key", "X-Tenant-Id": "tenant-demo"},
    )
    assert res_demo.status_code == 200
    data_demo = res_demo.json()
    assert data_demo["tenant_id"] == "tenant-demo"
    assert isinstance(data_demo["events"], list)
    for evt in data_demo["events"]:
        assert evt["tenant_id"] == "tenant-demo"

    # Read audit events for tenant-alt
    res_alt = client.get(
        "/v1/audit/events?limit=10",
        headers={"X-API-Key": "alt-key", "X-Tenant-Id": "tenant-alt"},
    )
    assert res_alt.status_code == 200
    data_alt = res_alt.json()
    assert data_alt["tenant_id"] == "tenant-alt"
    for evt in data_alt["events"]:
        assert evt["tenant_id"] == "tenant-alt"
