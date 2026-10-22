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
