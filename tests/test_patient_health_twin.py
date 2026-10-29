import pytest
from starlette.testclient import TestClient
from app.main import app
from app.services.patient_health_twin import PatientHealthTwinService, patient_health_twin_service


def test_patient_health_twin_default_profile():
    service = PatientHealthTwinService()
    profile = service.get_profile()
    assert profile.patient_id == "demo-patient-001"
    assert len(profile.organs) >= 8
    head_organ = next((o for o in profile.organs if o.id == "head"), None)
    assert head_organ is not None
    assert head_organ.vietnamese_name == "Đầu & Thần kinh"
    assert head_organ.coordinates.x == 50.0
    assert head_organ.coordinates.y == 11.0


def test_patient_health_twin_recovery():
    service = PatientHealthTwinService()
    res = service.evaluate_progress("Hôm nay tôi đã hết đau đầu và sổ mũi rồi, thấy khỏe hơn nhiều")
    assert res["status"] == "success"
    assert res["detected_event"] == "recovery"
    profile = res["profile"]
    assert profile.overall_health_score >= 90
    assert profile.health_trend == "improving"
    head = next(o for o in profile.organs if o.id == "head")
    assert head.status == "normal"
    assert head.pain_level == 0
    assert len(profile.timeline) >= 2


def test_patient_health_twin_adr_stomach():
    service = PatientHealthTwinService()
    res = service.evaluate_progress("Uống thuốc vào bỗng bị đau dạ dày dữ dội, cồn cào và buồn nôn")
    assert res["status"] == "success"
    assert res["detected_event"] == "adverse_reaction"
    assert res["must_discontinue_previous"] is True
    profile = res["profile"]
    assert profile.health_trend == "critical_alert"
    assert profile.safe_guardrail_alert is not None
    assert "HẠN CHẾ" in profile.safe_guardrail_alert.title or "AI BẢO VỆ" in profile.safe_guardrail_alert.title
    stomach = next(o for o in profile.organs if o.id == "stomach")
    assert stomach.status == "adverse_reaction"
    assert stomach.is_adverse_reaction is True
    assert stomach.pain_level >= 7
    assert len(profile.discontinued_medications) > 0


def test_patient_health_twin_scenario_switch():
    service = PatientHealthTwinService()
    # Scenario: ADR stomach
    p1 = service.switch_scenario("adr_stomach_nsaid")
    assert p1.safe_guardrail_alert is not None
    stomach = next(o for o in p1.organs if o.id == "stomach")
    assert stomach.status == "adverse_reaction"

    # Scenario: Recovered
    p2 = service.switch_scenario("recovered_headache")
    assert p2.overall_health_score >= 90
    assert p2.safe_guardrail_alert is None

    # Scenario: Healthy
    p3 = service.switch_scenario("healthy_baseline")
    assert p3.overall_health_score == 98


def test_health_twin_api_endpoints():
    client = TestClient(app)
    headers = {"x-api-key": "demo-key", "x-tenant-id": "tenant-demo"}

    # 1. GET /v1/health-twin/profile
    resp = client.get("/v1/health-twin/profile", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "overall_health_score" in data
    assert "organs" in data
    assert len(data["organs"]) >= 8

    # 2. POST /v1/health-twin/evaluate-symptom-update
    resp2 = client.post(
        "/v1/health-twin/evaluate-symptom-update",
        headers=headers,
        json={"message": "Tôi uống thuốc xong bị đau dạ dày dữ dội cồn cào"},
    )
    assert resp2.status_code == 200
    res_data = resp2.json()
    assert res_data["detected_event"] == "adverse_reaction"
    assert res_data["must_discontinue_previous"] is True
    assert res_data["profile"]["safe_guardrail_alert"] is not None

    # 3. POST /v1/health-twin/scenario
    resp3 = client.post(
        "/v1/health-twin/scenario",
        headers=headers,
        json={"scenario_id": "recovered_headache"},
    )
    assert resp3.status_code == 200
    sc_data = resp3.json()
    assert sc_data["overall_health_score"] >= 90

    # 4. POST /v1/health-twin/reset
    resp_reset = client.post("/v1/health-twin/reset", headers=headers)
    assert resp_reset.status_code == 200
    reset_data = resp_reset.json()
    assert reset_data["overall_health_score"] == 98

    # 5. Dynamic User Symptom Input: "Tôi bị đau rát họng và sốt 38.5 độ"
    resp_dyn = client.post(
        "/v1/health-twin/evaluate-symptom-update",
        headers=headers,
        json={"message": "Tôi bị đau rát họng và sốt 38.5 độ"},
    )
    assert resp_dyn.status_code == 200
    dyn_data = resp_dyn.json()
    assert dyn_data["status"] == "success"
    ent_organ = next(o for o in dyn_data["profile"]["organs"] if o["id"] == "ent")
    assert ent_organ["status"] == "inflamed"
    assert dyn_data["profile"]["vitals"]["temperature_celsius"] == 38.5

    # 6. Dynamic Vaccine Input: "Tôi chưa tiêm phòng viêm gan b"
    resp_hbv = client.post(
        "/v1/health-twin/evaluate-symptom-update",
        headers=headers,
        json={"message": "Tôi chưa tiêm phòng vắc-xin viêm gan B"},
    )
    assert resp_hbv.status_code == 200
    hbv_data = resp_hbv.json()
    liver_organ = next(o for o in hbv_data["profile"]["organs"] if o["id"] == "liver")
    assert liver_organ["future_risk"]["risk_level"] == "high"
    assert "CHƯA TIÊM PHÒNG" in liver_organ["future_risk"]["vaccination_status"]
