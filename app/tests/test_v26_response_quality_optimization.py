from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models.chat import GroundedAnswer
from app.services.conversation_continuation import resolve_conversation_continuation
from app.services.response_quality_overlay import enhance_response_answer


client = TestClient(app)


def _base_answer(summary: str = "Kết quả") -> GroundedAnswer:
    return GroundedAnswer(
        title="Kết quả",
        summary=summary,
        decision_basis="workflow_record",
        evidence_state="operation_confirmed",
    )


def _headers(key: str) -> dict[str, str]:
    return {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "Idempotency-Key": key,
        "X-Consent-Token": "consent-v26-quality",
    }


def test_half_tablet_question_owns_medication_safety_domain() -> None:
    resolution = resolve_conversation_continuation([
        ("user", "Tôi từng dị ứng penicillin, giờ có đơn amoxicillin thì có an toàn không?"),
        ("assistant", "Không tự thử thuốc nếu từng có phản ứng dị ứng."),
        ("user", "Tôi chưa uống viên amoxicillin nào, có nên thử nửa viên xem sao không?"),
    ])
    assert resolution is not None
    assert resolution.intent == "safety"


def test_self_induced_vomiting_after_ingestion_owns_safety_domain() -> None:
    resolution = resolve_conversation_continuation([
        ("user", "Tôi lỡ uống nhầm gấp đôi thuốc của mình cách đây khoảng 20 phút."),
        ("assistant", "Cần đánh giá an toàn thuốc."),
        ("user", "Tôi có nên tự gây nôn để đẩy thuốc ra không?"),
    ])
    assert resolution is not None
    assert resolution.intent == "safety"


def test_explicit_domain_switch_to_warfarin_ibuprofen_is_safety() -> None:
    resolution = resolve_conversation_continuation([
        ("user", "Tôi hơi đau đầu sau khi làm việc máy tính."),
        ("assistant", "Theo dõi triệu chứng."),
        ("user", "Chuyển việc khác: tôi đang dùng warfarin, có dùng ibuprofen được không?"),
    ])
    assert resolution is not None
    assert resolution.intent == "safety"
    assert resolution.reason == "explicit_domain_switch_to_medication_safety"


def test_monitoring_emergency_overlay_is_actionable_and_zero_question() -> None:
    answer = enhance_response_answer(
        _base_answer("Mức chuyển tuyến hiện tại: EMERGENCY"),
        intent="monitoring",
        status="answered",
        result={"escalation_level": "EMERGENCY", "urgency": "EMERGENCY", "trend": "worsening"},
    )
    assert answer.next_steps
    assert "115" in answer.next_steps[0] or "Cấp cứu" in answer.next_steps[0]
    assert answer.questions == []
    assert "nguy cơ cao" in answer.summary


def test_monitoring_urgent_overlay_has_same_day_action() -> None:
    answer = enhance_response_answer(
        _base_answer(),
        intent="monitoring",
        status="answered",
        result={"escalation_level": "URGENT", "urgency": "URGENT", "trend": "worsening"},
    )
    joined = " ".join(answer.next_steps).lower()
    assert "đánh giá sớm" in joined
    assert "trong ngày" in joined
    assert answer.safety_notes


def test_schedule_overlay_adds_verification_step_without_mutating_state() -> None:
    result = {
        "action": "create",
        "schedules": [{"schedule_id": "s-1", "status": "active"}],
    }
    answer = enhance_response_answer(
        _base_answer("Đã tạo card"),
        intent="schedule",
        status="answered",
        result=result,
    )
    assert any("kiểm tra" in step.lower() for step in answer.next_steps)
    assert result["schedules"][0]["schedule_id"] == "s-1"


def test_followup_without_plan_is_actionable_without_inventing_interval() -> None:
    answer = enhance_response_answer(
        _base_answer("Không có quy tắc phù hợp để sinh mốc tái khám."),
        intent="followup",
        status="answered",
        result={"plan_available": False, "suggestions": []},
    )
    text = " ".join([*answer.next_steps, *answer.questions]).lower()
    assert "cơ sở điều trị" in text
    assert "bác sĩ" in text
    assert not any(token in text for token in ("sau 3 ngày", "sau 7 ngày", "sau 14 ngày"))


def test_full_chat_explicit_medication_switch_routes_to_safety() -> None:
    response = client.post(
        "/v1/chat",
        headers=_headers("v26-switch-safety"),
        json={
            "conversation_id": "v26-switch-safety",
            "messages": [
                {"role": "user", "content": "Tôi hơi đau đầu sau khi làm việc máy tính."},
                {"role": "assistant", "content": "Bạn có thể nghỉ và theo dõi."},
                {"role": "user", "content": "Chuyển việc khác: tôi đang dùng warfarin, có dùng ibuprofen được không?"},
            ],
            "context": {"patient_ref": "V26-SWITCH"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "safety"
