from __future__ import annotations

from app.models.chat import ChatResponse, GroundedAnswer


def _answer(title: str = "Kết quả xử lý") -> GroundedAnswer:
    return GroundedAnswer(
        title=title,
        summary="Đã xử lý yêu cầu theo dữ liệu hiện có.",
        decision_basis="workflow_record",
        evidence_state="operation_confirmed",
    )


def test_monitoring_emergency_gets_structured_immediate_action() -> None:
    response = ChatResponse(
        request_id="v26-monitor-emergency",
        conversation_id="v26-monitor-emergency",
        status="answered",
        intent="monitoring",
        reply="Chỉ số ở mức cấp cứu.",
        result={"escalation_level": "EMERGENCY"},
        answer=_answer("Chỉ số nằm trong vùng cần đánh giá cấp cứu"),
    )

    assert response.answer is not None
    assert response.answer.next_steps
    assert "115" in response.answer.next_steps[0]
    assert response.answer.questions == []
    assert response.answer.display_questions == []


def test_monitoring_urgent_gets_structured_early_evaluation_action() -> None:
    response = ChatResponse(
        request_id="v26-monitor-urgent",
        conversation_id="v26-monitor-urgent",
        status="answered",
        intent="monitoring",
        reply="Chỉ số cần đánh giá sớm.",
        result={"escalation_level": "URGENT"},
        answer=_answer("Chỉ số cần được đánh giá sớm"),
    )

    assert response.answer is not None
    assert response.answer.next_steps
    assert "đánh giá sớm" in response.answer.next_steps[0]


def test_schedule_success_gets_structured_followup_action() -> None:
    response = ChatResponse(
        request_id="v26-schedule",
        conversation_id="v26-schedule",
        status="answered",
        intent="schedule",
        reply="Đã tạo lịch uống thuốc.",
        result={"schedule_id": "S-1"},
        answer=_answer("Đã cập nhật lịch uống thuốc"),
    )

    assert response.answer is not None
    assert response.answer.next_steps
    assert "đổi giờ" in response.answer.next_steps[0]


def test_unsupported_safety_response_still_has_safe_next_action() -> None:
    response = ChatResponse(
        request_id="v26-safety-boundary",
        conversation_id="v26-safety-boundary",
        status="unsupported",
        intent="safety",
        reply="Không thể kê liều cá nhân hóa.",
        result=None,
        answer=GroundedAnswer(
            title="Mình chưa thể xử lý yêu cầu này",
            summary="Không thể kê liều cá nhân hóa từ hội thoại.",
            decision_basis="insufficient_information",
            evidence_state="partial_input",
        ),
    )

    assert response.answer is not None
    assert response.answer.next_steps
    assert "bác sĩ hoặc dược sĩ" in response.answer.next_steps[0]
