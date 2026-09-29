from __future__ import annotations

from app.services.answering import build_grounded_answer


def test_schedule_workflow_exposes_structured_next_step() -> None:
    answer = build_grounded_answer(
        intent="schedule",
        status="answered",
        reply="Đã thêm 1 mốc uống aspirin vào card lịch thuốc.",
        required_fields=[],
        result={"operation": "created", "active_count": 1},
    )

    assert answer.next_steps
    assert "kiểm tra" in answer.next_steps[0].lower()
    assert "card" in answer.next_steps[0].lower()
    assert any("Bạn nên làm gì lúc này" in block.text for block in answer.narrative)


def test_needs_information_has_action_plan_and_question() -> None:
    answer = build_grounded_answer(
        intent="safety",
        status="needs_information",
        reply="Tôi cần tên thuốc đang cân nhắc hoặc thuốc muốn phối hợp để kiểm tra.",
        required_fields=["proposed_medications"],
        result=None,
    )

    assert answer.next_steps
    assert answer.questions
    assert "kiểm tra lại yêu cầu" in answer.next_steps[0].lower()


def test_low_risk_safety_answer_still_has_safe_next_step() -> None:
    answer = build_grounded_answer(
        intent="safety",
        status="answered",
        reply="Đã kiểm tra an toàn thuốc.",
        required_fields=[],
        result={
            "overall_risk": "LOW",
            "urgency": "ROUTINE",
            "warnings": [],
            "unknown_ingredients": [],
            "requires_human_review": False,
            "clarifying_questions": [],
        },
    )

    assert answer.next_steps
    assert "bác sĩ" in answer.next_steps[0].lower() or "dược sĩ" in answer.next_steps[0].lower()


def test_monitoring_none_provides_concrete_tracking_action() -> None:
    answer = build_grounded_answer(
        intent="monitoring",
        status="answered",
        reply="Đã đọc chỉ số.",
        required_fields=[],
        result={
            "escalation_level": "NONE",
            "urgency": "ROUTINE",
            "trend": "stable",
            "alerts": [],
        },
    )

    assert answer.next_steps
    assert "theo dõi" in answer.next_steps[0].lower()
    assert "ghi lại" in answer.next_steps[0].lower()


def test_monitoring_emergency_is_action_first_and_zero_question() -> None:
    answer = build_grounded_answer(
        intent="monitoring",
        status="answered",
        reply="Chỉ số ở mức cảnh báo.",
        required_fields=[],
        result={
            "escalation_level": "EMERGENCY",
            "urgency": "EMERGENCY",
            "trend": "worsening",
            "alerts": [
                {
                    "metric": "spo2",
                    "severity": "HIGH",
                    "detail": "SpO2 rất thấp, cần đánh giá cấp cứu ngay.",
                    "basis": "threshold",
                    "confidence": 1.0,
                }
            ],
        },
    )

    assert answer.next_steps
    assert "115" in answer.next_steps[0] or "Cấp cứu" in answer.next_steps[0]
    assert answer.questions == []
    assert answer.narrative
    first = answer.narrative[0].text.lower()
    assert "115" in first or "cấp cứu" in first


def test_followup_workflow_has_confirmation_action() -> None:
    answer = build_grounded_answer(
        intent="followup",
        status="answered",
        reply="Đã lập kế hoạch tái khám sau xuất viện.",
        required_fields=[],
        result={"status": "planned"},
    )

    assert answer.next_steps
    assert "kiểm tra" in answer.next_steps[0].lower()
    assert "liên hệ" in answer.next_steps[0].lower()
