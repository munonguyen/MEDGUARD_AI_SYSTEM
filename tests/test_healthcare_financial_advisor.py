import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.healthcare_financial_advisor import (
    healthcare_financial_advisor_service,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_safety_gate_detects_red_flags():
    """Safety Gate must intercept severe symptoms and force urgent doctor consultation."""
    user_msg = "Tôi bị đau thắt ngực khó thở dữ dội từ sáng đến giờ, có thuốc nào rẻ uống đỡ tốn tiền không?"
    status, revised_advice = healthcare_financial_advisor_service.evaluate_clinical_safety_and_positivity(
        user_message=user_msg,
        proposed_advice="Bạn có thể mua vài viên giảm đau ngoài tiệm.",
    )

    assert not status.is_safe
    assert status.safety_tier == "urgent_medical_attention"
    assert status.clinical_override_applied is True
    assert len(status.red_flags_detected) >= 2
    assert "CẢNH BÁO AN TOÀN LÂM SÀNG" in revised_advice
    assert "BHYT" in revised_advice


def test_safety_gate_blocks_dangerous_reassurance_phrases():
    """Safety Gate must scrub phrases that tell users not to see doctors or not buy medicine."""
    user_msg = "Tôi bị đau đầu âm ỉ cả tuần nay."
    dangerous_advice = "Không sao đâu, bạn không cần đi khám và không cần mua thuốc, ở nhà tự khỏi để tiết kiệm."
    status, revised_advice = healthcare_financial_advisor_service.evaluate_clinical_safety_and_positivity(
        user_message=user_msg,
        proposed_advice=dangerous_advice,
    )

    assert status.safety_tier == "caution"
    assert status.clinical_override_applied is True
    assert "không cần đi khám" not in revised_advice
    assert "không cần mua thuốc" not in revised_advice
    assert "chuẩn GPP" in revised_advice or "thăm khám" in revised_advice


def test_chat_extraction_syncs_financial_signals():
    """Zero-friction chat sync must capture recurrence waste and unofficial sources."""
    healthcare_financial_advisor_service.reset_to_default("guest_patient")
    chat_msg = "Tôi uống 4 ngày chưa đỡ, vừa ra tiệm thuốc đầu ngõ mua liều lẻ hết 150k"

    sync_result = healthcare_financial_advisor_service.extract_and_sync_from_chat(chat_msg)
    assert sync_result["has_financial_signal"] is True
    assert sync_result["detected_amount_vnd"] == 150000
    assert sync_result["recurrence_flag"] is True
    assert sync_result["is_official_gpp"] is False

    assessment = healthcare_financial_advisor_service.get_assessment("guest_patient")
    # Latest transaction must be the newly extracted chat transaction
    assert assessment.transactions[0].amount_vnd == 150000
    assert assessment.transactions[0].recurrence_flag is True
    assert assessment.breakdown.recurrence_waste_spent_vnd > 0


def test_financial_assessment_endpoint(client):
    """GET /v1/financial/assessment must return realistic breakdown and recommendations."""
    res = client.get(
        "/v1/financial/assessment",
        headers={"x-api-key": "demo-key", "x-tenant-id": "tenant-demo"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "breakdown" in data
    assert "treatment_efficiency_score" in data
    assert data["treatment_efficiency_score"] > 0
    assert len(data["recommendations"]) >= 3
    assert len(data["transactions"]) >= 5


def test_evaluate_safety_endpoint(client):
    """POST /v1/financial/evaluate-safety must return evaluated safety status."""
    payload = {
        "user_message": "Sốt cao 4 ngày kèm ho ra máu",
        "proposed_advice": "Uống nhiều nước ấm để tiết kiệm tiền khám.",
    }
    res = client.post(
        "/v1/financial/evaluate-safety",
        json=payload,
        headers={"x-api-key": "demo-key", "x-tenant-id": "tenant-demo"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["safety_status"]["safety_tier"] == "urgent_medical_attention"
    assert "CẢNH BÁO AN TOÀN LÂM SÀNG" in data["revised_advice"]


def test_detect_budget_target():
    """Service must accurately parse Vietnamese healthcare budget phrasing."""
    svc = healthcare_financial_advisor_service
    # User's exact prompt
    target_1 = svc.detect_budget_target(
        "tổng chi tiêu tháng này tôi muốn là tối đa khoảng 3 triệu vào việc mua thuốc và khám sức khoẻ"
    )
    assert target_1 == 3_000_000

    target_2 = svc.detect_budget_target("hạn mức chi tiêu y tế tháng này 2.5 triệu")
    assert target_2 == 2_500_000

    target_3 = svc.detect_budget_target("ngân sách thuốc và khám tháng 10 là 2tr5")
    assert target_3 == 2_500_000

    target_4 = svc.detect_budget_target("chi tiêu tối đa 5.000.000 đ cho khám chữa bệnh")
    assert target_4 == 5_000_000


def test_set_budget_endpoint(client):
    """POST /v1/financial/set-budget updates budget and generates clinical allocation plan."""
    payload = {
        "patient_ref": "test_patient",
        "budget_target_vnd": 3000000,
    }
    res = client.post(
        "/v1/financial/set-budget",
        json=payload,
        headers={"x-api-key": "demo-key", "x-tenant-id": "tenant-demo"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["monthly_budget_target_vnd"] == 3000000
    assert data["remaining_budget_vnd"] > 0
    assert data["budget_status"] == "within_budget"
    assert "budget_allocation_plan" in data
    assert data["budget_allocation_plan"]["doctor_consult_vnd"] == 1350000
    assert data["budget_allocation_plan"]["gpp_medication_vnd"] == 1050000


def test_chat_budget_statement_intercepted(client):
    """Chat must intercept budget statements and return financial guidance instead of symptom fallback."""
    chat_payload = {
        "conversation_id": "conv-test-budget-01",
        "messages": [
            {
                "role": "user",
                "content": "tổng chi tiêu tháng này tôi muốn là tối đa khoảng 3 triệu vào việc mua thuốc và khám sức khoẻ",
            }
        ],
        "context": {"patient_ref": "guest_patient"},
    }
    res = client.post(
        "/v1/chat",
        json=chat_payload,
        headers={
            "x-api-key": "demo-key",
            "x-tenant-id": "tenant-demo",
            "Idempotency-Key": "test-budget-idempotency-01",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "answered"
    assert data["intent"] == "financial"
    assert "3.000.000" in data["reply"]
    assert "view=spending" in data["reply"]
    # Ensure it did NOT trigger the generic triage fallback
    assert "Gateway không đạt kiểm định" not in data["reply"]
    assert "THÔNG BÁO CHƯA ĐỦ THÔNG TIN: Dữ liệu bạn cung cấp hiện chưa đủ" not in data["reply"]

    # Verify financial_assessment_update is included in answer
    assert "financial_assessment_update" in data["answer"]
    fin = data["answer"]["financial_assessment_update"]
    assert fin["assessment"]["monthly_budget_target_vnd"] == 3000000


def test_chat_update_budget_to_10_million_and_suppress_irrelevant_cards(client):
    """
    When updating budget to 10 million:
    1. Budget must update to 10.000.000đ and persist across assessment fetch.
    2. No unwanted medication proposal (medication_suitability is None).
    3. No unwanted map routing (geo_routing is None).
    4. Follow-up suggestions must be financial, NOT dental/toothache.
    """
    chat_payload = {
        "conversation_id": "conv-test-budget-10m",
        "messages": [
            {
                "role": "user",
                "content": "tổng chi tiêu tháng này tôi muốn là tối đa khoảng 10 triệu vào việc mua thuốc và khám sức khoẻ",
            }
        ],
        "context": {"patient_ref": "guest_patient"},
    }
    res = client.post(
        "/v1/chat",
        json=chat_payload,
        headers={
            "x-api-key": "demo-key",
            "x-tenant-id": "tenant-demo",
            "Idempotency-Key": "test-budget-10m-01",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "answered"
    assert data["intent"] == "financial"
    assert "10.000.000" in data["reply"]
    assert "view=spending" in data["reply"]

    # Verify no unwanted cards attached
    answer = data["answer"]
    assert answer.get("medication_suitability") is None
    assert answer.get("geo_routing") is None

    # Verify follow-ups are financial, not dental
    followups = answer.get("suggested_followups", [])
    assert any("BHYT" in f or "tiết kiệm" in f for f in followups)
    assert not any("răng" in f.lower() or "nha sĩ" in f.lower() for f in followups)

    # Verify assessment persisted in backend and can be retrieved via GET
    get_res = client.get(
        "/v1/financial/assessment?patient_ref=guest_patient",
        headers={"x-api-key": "demo-key", "x-tenant-id": "tenant-demo"},
    )
    assert get_res.status_code == 200
    assess_data = get_res.json()
    assert assess_data["monthly_budget_target_vnd"] == 10000000


