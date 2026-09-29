from __future__ import annotations

from app.models.chat import ChatResponse, GroundedAnswer
from app.services.conversation_continuation import resolve_conversation_continuation


def _answer() -> GroundedAnswer:
    return GroundedAnswer(
        title="Kết quả",
        summary="Đã xử lý.",
        decision_basis="workflow_record",
        evidence_state="operation_confirmed",
    )


def test_schedule_answer_exposes_structured_next_step() -> None:
    response = ChatResponse(
        request_id="v26-schedule",
        conversation_id="v26-schedule",
        status="answered",
        intent="schedule",
        reply="Đã tạo card.",
        result={"action": "create", "schedules": []},
        answer=_answer(),
    )
    assert response.answer is not None
    assert response.answer.next_steps
    assert "card" in response.answer.next_steps[0].lower()
    assert "kiểm tra" in response.answer.next_steps[0].lower()


def test_monitoring_urgent_exposes_structured_action_plan() -> None:
    response = ChatResponse(
        request_id="v26-monitoring",
        conversation_id="v26-monitoring",
        status="answered",
        intent="monitoring",
        reply="Chỉ số cần đánh giá sớm.",
        result={"escalation_level": "URGENT", "urgency": "URGENT"},
        answer=_answer(),
    )
    assert response.answer is not None
    assert response.answer.next_steps
    step = response.answer.next_steps[0].lower()
    assert "cơ sở y tế" in step
    assert "đánh giá sớm" in step


def test_monitoring_emergency_action_plan_keeps_zero_question_policy() -> None:
    answer = _answer().model_copy(update={"questions": ["Bạn đo lại lúc nào?"]})
    response = ChatResponse(
        request_id="v26-monitoring-emergency",
        conversation_id="v26-monitoring-emergency",
        status="answered",
        intent="monitoring",
        reply="Chỉ số ở vùng cấp cứu.",
        result={"escalation_level": "EMERGENCY", "urgency": "EMERGENCY"},
        answer=answer,
    )
    assert response.answer is not None
    assert response.answer.next_steps
    assert "cấp cứu" in response.answer.next_steps[0].lower()
    assert response.answer.questions == []
    assert response.answer.display_questions == []


def test_half_tablet_trial_is_owned_by_medication_safety() -> None:
    resolution = resolve_conversation_continuation(
        [("user", "Tôi bị đau họng."), ("user", "Tôi chưa uống amoxicillin, có nên thử nửa viên xem sao không?")]
    )
    assert resolution is not None
    assert resolution.intent == "safety"


def test_self_induced_vomiting_is_owned_by_medication_safety() -> None:
    resolution = resolve_conversation_continuation(
        [("user", "Tôi vừa uống nhầm thuốc."), ("user", "Tôi có nên tự gây nôn để đẩy thuốc ra không?")]
    )
    assert resolution is not None
    assert resolution.intent == "safety"


def test_two_drug_compatibility_question_owns_new_domain() -> None:
    resolution = resolve_conversation_continuation(
        [
            ("user", "Tôi đau đầu nhẹ sau khi nhìn màn hình lâu."),
            ("user", "Chuyển việc khác: tôi đang dùng warfarin, có dùng ibuprofen được không?"),
        ]
    )
    assert resolution is not None
    assert resolution.intent == "safety"
    assert resolution.confidence >= 0.99
