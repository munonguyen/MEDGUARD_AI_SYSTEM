import base64
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.queue import job_queue
from app.services.audit import audit_store
from app.services.circuit import CircuitBreaker, CircuitState, model_circuit
from app.services.idempotency import idempotency_store
from app.services.jobs import job_store
from app.workers.ocr_worker import process_next_ocr_job


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_dev_state():
    audit_store.clear()
    idempotency_store.clear()
    job_store.clear()
    job_queue.clear()
    model_circuit.reset()
    yield


def auth_headers():
    return {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "Idempotency-Key": "idem-1",
        "X-Request-Id": "req-test-1",
    }


def test_health():
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_protected_endpoint_requires_headers():
    response = client.post(
        "/v1/triage",
        json={"patient_ref": "p1", "symptoms_text": "đau bụng"},
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "missing_auth_headers"
    assert response.headers["X-Request-Id"].startswith("req_")


def test_protected_endpoint_rejects_wrong_tenant_key_pair():
    headers = auth_headers()
    headers["X-Tenant-Id"] = "tenant-unknown"
    response = client.post(
        "/v1/triage",
        headers=headers,
        json={"patient_ref": "p1", "symptoms_text": "đau bụng"},
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "tenant_not_enabled"


def test_invalid_idempotency_key_is_rejected():
    headers = auth_headers()
    headers["Idempotency-Key"] = "invalid key"
    response = client.post(
        "/v1/triage",
        headers=headers,
        json={"patient_ref": "p1", "symptoms_text": "đau bụng"},
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "invalid_idempotency_key"


def test_idempotency_returns_prior_response_for_same_payload():
    payload = {"patient_ref": "p1", "symptoms_text": "đau bụng"}
    first = client.post("/v1/triage", headers=auth_headers(), json=payload)
    second = client.post("/v1/triage", headers=auth_headers(), json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_idempotency_rejects_different_payload_with_same_key():
    headers = auth_headers()
    first = client.post(
        "/v1/triage",
        headers=headers,
        json={"patient_ref": "p1", "symptoms_text": "đau bụng"},
    )
    second = client.post(
        "/v1/triage",
        headers=headers,
        json={"patient_ref": "p1", "symptoms_text": "khó thở"},
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error_code"] == "idempotency_conflict"


def test_triage_emergency():
    response = client.post(
        "/v1/triage",
        headers=auth_headers(),
        json={
            "patient_ref": "p1",
            "symptoms_text": "Đau ngực lan tay trái và khó thở",
            "age": 58,
            "sex": "male",
            "known_conditions": ["tăng huyết áp"],
            "current_medications": [],
            "vitals": {"systolic": 165, "diastolic": 96, "heart_rate": 102, "temperature_c": 37.1},
            "locale": "vi-VN",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["urgency"] == "EMERGENCY"
    assert body["emergency_flag"] is True
    assert "đau ngực" in " ".join(body["red_flags"]).lower()


def test_safety_allergy_and_interaction():
    response = client.post(
        "/v1/medication/safety-check",
        headers=auth_headers(),
        json={
            "patient_ref": "p2",
            "age": 44,
            "sex": "female",
            "allergies": [{"substance": "Penicillin", "reaction": "mề đay", "severity": "HIGH"}],
            "conditions": ["loét dạ dày"],
            "current_medications": [{"name": "Aspirin 81mg", "active_ingredient": "aspirin", "dose_mg": 81}],
            "proposed_medications": [
                {"name": "Augmentin 625mg", "active_ingredient": "amoxicillin", "dose_mg": 625},
                {"name": "Ibuprofen 400mg", "active_ingredient": "ibuprofen", "dose_mg": 400},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["overall_risk"] in {"MODERATE", "HIGH"}
    assert body["requires_human_review"] is True
    assert len(body["warnings"]) >= 1


def test_queue_prioritizes_emergency_before_urgent_and_routine():
    response = client.post(
        "/v1/queue/prioritize",
        headers=auth_headers(),
        json={
            "items": [
                {"patient_ref": "routine", "urgency": "ROUTINE", "wait_minutes": 120},
                {"patient_ref": "urgent", "urgency": "URGENT", "esi_level": 3},
                {"patient_ref": "emergency", "urgency": "EMERGENCY", "emergency_flag": True, "esi_level": 2},
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert [item["patient_ref"] for item in body["items"]] == ["emergency", "urgent", "routine"]
    assert body["items"][0]["rank"] == 1
    assert body["trace"]["rule_version"] == "queue-priority-rules@pha0"


def test_idempotency_is_scoped_by_tenant():
    payload = {"patient_ref": "same-ref", "symptoms_text": "đau bụng"}
    first = client.post("/v1/triage", headers=auth_headers(), json=payload)
    alternate_headers = auth_headers()
    alternate_headers.update({"X-Tenant-Id": "tenant-alt", "X-API-Key": "alt-key"})
    second = client.post("/v1/triage", headers=alternate_headers, json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["trace"]["tenant_id"] == "tenant-demo"
    assert second.json()["trace"]["tenant_id"] == "tenant-alt"


def test_prescription_extract_queues_without_persisting_image_content():
    response = client.post(
        "/v1/prescription/extract",
        headers=auth_headers(),
        files={"image": ("prescription.png", b"fake-image-bytes", "image/png")},
        data={"patient_ref": "p3", "catalog_ref": "catalog-demo"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["poll_url"].endswith(body["job_id"])

    status_response = client.get(
        f"/v1/jobs/{body['job_id']}",
        headers={"X-API-Key": "demo-key", "X-Tenant-Id": "tenant-demo"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "queued"
    job = job_store.jobs[("tenant-demo", body["job_id"])]
    assert not hasattr(job, "image_bytes")


def test_job_is_not_visible_across_tenants():
    response = client.post(
        "/v1/prescription/extract",
        headers=auth_headers(),
        files={"image": ("prescription.png", b"fake-image-bytes", "image/png")},
        data={"patient_ref": "p4"},
    )
    job_id = response.json()["job_id"]
    alternate_headers = {"X-API-Key": "alt-key", "X-Tenant-Id": "tenant-alt"}
    status_response = client.get(f"/v1/jobs/{job_id}", headers=alternate_headers)
    assert status_response.status_code == 404
    assert status_response.json()["error_code"] == "job_not_found"


def test_prescription_extract_is_idempotent_and_detects_conflict():
    image = ("prescription.png", b"same-image", "image/png")
    first = client.post(
        "/v1/prescription/extract",
        headers=auth_headers(),
        files={"image": image},
        data={"patient_ref": "p5"},
    )
    second = client.post(
        "/v1/prescription/extract",
        headers=auth_headers(),
        files={"image": image},
        data={"patient_ref": "p5"},
    )
    conflict = client.post(
        "/v1/prescription/extract",
        headers=auth_headers(),
        files={"image": ("prescription.png", b"different-image", "image/png")},
        data={"patient_ref": "p5"},
    )
    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json() == first.json()
    assert conflict.status_code == 409
    assert conflict.json()["error_code"] == "idempotency_conflict"


def test_followup_returns_rule_based_plan_and_unknown_without_match():
    matched = client.post(
        "/v1/followup/plan",
        headers=auth_headers(),
        json={
            "patient_ref": "p-followup",
            "diagnosis_text": "viêm phổi",
            "discharge_date": "2026-09-07",
        },
    )
    assert matched.status_code == 200
    assert matched.json()["plan_available"] is True
    assert matched.json()["suggestions"][0]["scheduled_for"] == "2026-09-10"
    assert matched.json()["suggestions"][0]["basis"] == "rule"

    unknown_headers = auth_headers()
    unknown_headers["Idempotency-Key"] = "followup-unknown"
    unknown = client.post(
        "/v1/followup/plan",
        headers=unknown_headers,
        json={"patient_ref": "p-followup", "diagnosis_text": "đau nhẹ thoáng qua"},
    )
    assert unknown.status_code == 200
    assert unknown.json()["status"] == "unknown"
    assert unknown.json()["plan_available"] is False
    assert unknown.json()["suggestions"] == []


def test_monitoring_insufficient_data_and_emergency_escalation():
    insufficient = client.post(
        "/v1/monitoring/ingest",
        headers=auth_headers(),
        json={
            "patient_ref": "p-monitor",
            "metrics": [
                {"metric": "spo2", "value": 96, "unit": "%", "recorded_at": "2026-09-07T08:00:00Z"},
                {"metric": "spo2", "value": 95, "unit": "%", "recorded_at": "2026-09-07T09:00:00Z"},
            ],
        },
    )
    assert insufficient.status_code == 200
    assert insufficient.json()["trend"] == "insufficient_data"
    assert insufficient.json()["status"] == "unknown"

    emergency_headers = auth_headers()
    emergency_headers["Idempotency-Key"] = "monitor-emergency"
    emergency = client.post(
        "/v1/monitoring/ingest",
        headers=emergency_headers,
        json={
            "patient_ref": "p-monitor",
            "metrics": [
                {"metric": "spo2", "value": 95, "unit": "%", "recorded_at": "2026-09-07T08:00:00Z"},
                {"metric": "spo2", "value": 90, "unit": "%", "recorded_at": "2026-09-07T09:00:00Z"},
                {"metric": "heart_rate", "value": 110, "unit": "bpm", "recorded_at": "2026-09-07T09:00:00Z"},
            ],
        },
    )
    assert emergency.status_code == 200
    assert emergency.json()["escalation_level"] == "EMERGENCY"
    assert emergency.json()["alerts"][0]["metric"] == "spo2"


def test_pharmacy_fulfillment_orders_options():
    response = client.post(
        "/v1/pharmacy/fulfillment",
        headers=auth_headers(),
        json={
            "patient_ref": "p-pharmacy",
            "medications": [{"name": "Amoxicillin", "active_ingredient": "amoxicillin", "quantity": 10}],
            "location_hint": "Quận 1, TP HCM",
            "preferred_mode": "pickup",
            "urgency": "ROUTINE",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["options"][0]["provider_code"] == "HCM-CENTRAL"
    assert body["options"][0]["availability"] == "AVAILABLE"
    assert body["needs_human_review"] is False


def test_result_delivery_prepares_webhook_signature():
    response = client.post(
        "/v1/result-delivery/prepare",
        headers=auth_headers(),
        json={"event_name": "triage.completed", "channel": "webhook", "target_ref": "client-hook", "body": {"ok": True}},
    )
    assert response.status_code == 200
    envelope = response.json()["envelope"]
    assert envelope["signed"] is True
    assert envelope["headers"]["X-MedGuard-Signature"].startswith("sha256=")
    assert envelope["headers"]["X-Request-Id"] == response.json()["request_id"]


def test_models_endpoint_has_active_development_registry_entry():
    response = client.get("/v1/models")
    assert response.status_code == 200
    body = response.json()
    assert body["models"][0]["name"] == "deterministic-rules"
    assert body["models"][0]["active"] is True
    serialized = str(body).lower()
    assert "gemini" not in serialized
    assert "openai" not in serialized
    assert "gpt" not in serialized


def test_circuit_breaker_transitions_and_recovers():
    breaker = CircuitBreaker(error_threshold=0.5, min_requests=2)
    assert breaker.state == CircuitState.CLOSED
    assert breaker.allow_request() is True
    breaker.record_failure()
    assert breaker.state == CircuitState.CLOSED
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    assert breaker.allow_request() is False
    breaker.opened_at = 0
    assert breaker.state == CircuitState.HALF_OPEN
    assert breaker.allow_request() is True
    breaker.record_success()
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


def test_ocr_worker_fails_closed_and_job_poll_exposes_failure():
    png_header = (
        base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==")
    )
    response = client.post(
        "/v1/prescription/extract",
        headers=auth_headers(),
        files={"image": ("prescription.png", png_header, "image/png")},
        data={"patient_ref": "p-worker"},
    )
    job_id = response.json()["job_id"]
    assert process_next_ocr_job() == job_id
    status_response = client.get(
        f"/v1/jobs/{job_id}",
        headers={"X-API-Key": "demo-key", "X-Tenant-Id": "tenant-demo"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "failed"
    assert status_response.json()["review_status"] == "FAILED"
    assert status_response.json()["error_code"] == "ocr_worker_unavailable"


def test_domain_operations_append_audit_events():
    response = client.post(
        "/v1/triage",
        headers=auth_headers(),
        json={"patient_ref": "p-audit", "symptoms_text": "đau bụng"},
    )
    assert response.status_code == 200
    assert any(event.action == "triage.evaluate" for event in audit_store.events)


# =====================================================================
# Knowledge-backed rule engine tests
# =====================================================================


def test_triage_routes_to_gastroenterology_for_abdominal_pain():
    response = client.post(
        "/v1/triage",
        headers=auth_headers(),
        json={"patient_ref": "p-gi", "symptoms_text": "đau bụng và buồn nôn liên tục"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["urgency"] == "ROUTINE"
    assert body["recommended_specialty"]["code"] == "GASTROENTEROLOGY"


def test_triage_routes_to_neurology_for_headache():
    headers = auth_headers()
    headers["Idempotency-Key"] = "neuro-1"
    response = client.post(
        "/v1/triage",
        headers=headers,
        json={"patient_ref": "p-neuro", "symptoms_text": "đau đầu kéo dài và chóng mặt"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["urgency"] == "ROUTINE"
    assert body["recommended_specialty"]["code"] == "NEUROLOGY"
    assert len(body["clarifying_questions"]) == 4
    assert body["self_care"]
    assert body["safety_net"]
    assert body["trace"]["details"]["symptom_guidance"] == "headache"


def test_triage_neurological_emergency_routes_to_neurology():
    headers = auth_headers()
    headers["Idempotency-Key"] = "neuro-emergency-1"
    response = client.post(
        "/v1/triage",
        headers=headers,
        json={"patient_ref": "p-stroke", "symptoms_text": "méo miệng đột ngột và nói khó"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["urgency"] == "EMERGENCY"
    assert body["emergency_flag"] is True
    assert body["recommended_specialty"]["code"] == "NEUROLOGY"


def test_triage_vital_only_emergency_without_text_red_flags():
    headers = auth_headers()
    headers["Idempotency-Key"] = "vital-emerg-1"
    response = client.post(
        "/v1/triage",
        headers=headers,
        json={
            "patient_ref": "p-vital",
            "symptoms_text": "mệt mỏi chung",
            "vitals": {"spo2": 85, "systolic": 190},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["urgency"] == "EMERGENCY"
    assert body["emergency_flag"] is True


def test_triage_response_includes_knowledge_version():
    headers = auth_headers()
    headers["Idempotency-Key"] = "kv-1"
    response = client.post(
        "/v1/triage",
        headers=headers,
        json={"patient_ref": "p-kv", "symptoms_text": "đau bụng nhẹ"},
    )
    body = response.json()
    assert "knowledge_version" in body["trace"]
    assert body["trace"]["knowledge_version"] != ""
    assert "knowledge_integrity" in body["trace"]["details"]


def test_safety_warfarin_aspirin_interaction_from_knowledge():
    headers = auth_headers()
    headers["Idempotency-Key"] = "warfarin-1"
    response = client.post(
        "/v1/medication/safety-check",
        headers=headers,
        json={
            "patient_ref": "p-warfarin",
            "current_medications": [{"name": "Warfarin 5mg", "active_ingredient": "warfarin"}],
            "proposed_medications": [{"name": "Aspirin 81mg", "active_ingredient": "aspirin"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["overall_risk"] == "HIGH"
    assert body["requires_human_review"] is True
    interaction_warnings = [w for w in body["warnings"] if w["type"] == "DRUG_DRUG_INTERACTION"]
    assert len(interaction_warnings) >= 1
    assert interaction_warnings[0]["severity"] == "HIGH"


def test_safety_simvastatin_clarithromycin_interaction():
    headers = auth_headers()
    headers["Idempotency-Key"] = "statin-macro-1"
    response = client.post(
        "/v1/medication/safety-check",
        headers=headers,
        json={
            "patient_ref": "p-statin",
            "current_medications": [{"name": "Simvastatin 20mg", "active_ingredient": "simvastatin"}],
            "proposed_medications": [{"name": "Klacid 500mg", "active_ingredient": "clarithromycin"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["overall_risk"] == "HIGH"
    assert any(w["type"] == "DRUG_DRUG_INTERACTION" for w in body["warnings"])


def test_safety_sulfonamide_allergy_cross_reactivity():
    headers = auth_headers()
    headers["Idempotency-Key"] = "sulfa-1"
    response = client.post(
        "/v1/medication/safety-check",
        headers=headers,
        json={
            "patient_ref": "p-sulfa",
            "allergies": [{"substance": "sulfonamide", "severity": "HIGH"}],
            "proposed_medications": [{"name": "Bactrim", "active_ingredient": "co-trimoxazole"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requires_human_review"] is True
    allergy_warnings = [w for w in body["warnings"] if "ALLERGY" in w["type"]]
    assert len(allergy_warnings) >= 1


def test_safety_nsaid_contraindication_with_renal_failure():
    headers = auth_headers()
    headers["Idempotency-Key"] = "ci-renal-1"
    response = client.post(
        "/v1/medication/safety-check",
        headers=headers,
        json={
            "patient_ref": "p-renal",
            "conditions": ["suy thận nặng"],
            "proposed_medications": [{"name": "Ibuprofen 400mg", "active_ingredient": "ibuprofen"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["overall_risk"] == "HIGH"
    ci_warnings = [w for w in body["warnings"] if w["type"] == "CONDITION_CONTRAINDICATION"]
    assert len(ci_warnings) >= 1


def test_safety_response_includes_knowledge_integrity():
    headers = auth_headers()
    headers["Idempotency-Key"] = "ki-safety-1"
    response = client.post(
        "/v1/medication/safety-check",
        headers=headers,
        json={
            "patient_ref": "p-ki",
            "proposed_medications": [{"name": "Paracetamol", "active_ingredient": "paracetamol"}],
        },
    )
    body = response.json()
    assert "knowledge_integrity" in body["trace"]["details"]
    assert "drug_interactions.json" in body["trace"]["details"]["knowledge_integrity"]


def test_knowledge_loader_integrity():
    from app.knowledge.loader import knowledge
    report = knowledge.integrity_report()
    assert "drug_interactions.json" in report
    assert "allergy_cross_matrix.json" in report
    assert "red_flag_protocols.json" in report
    assert "contraindications.json" in report
    for name, info in report.items():
        assert "version" in info
        assert "sha256" in info
        assert len(info["sha256"]) == 64  # SHA-256 hex
