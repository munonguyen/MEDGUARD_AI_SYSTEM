from __future__ import annotations

from app.services.answering import build_grounded_answer
from app.services.contextual_triage_planner import build_contextual_triage_plan
from app.services.professional_response_gate import evaluate_professional_response


def test_emergency_triage_narrative_is_action_first_and_zero_question() -> None:
    answer = build_grounded_answer(
        intent="triage",
        status="answered",
        reply="Đã phân luồng cấp cứu.",
        required_fields=[],
        result={
            "urgency": "EMERGENCY",
            "emergency_flag": True,
            "esi_level": 1,
            "red_flags": ["đau ngực lan tay trái kèm vã mồ hôi và khó thở"],
            "advice": "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức; không tự lái xe.",
            "clarifying_questions": ["Bạn đau từ khi nào?"],
            "safety_net": [],
            "self_care": [],
        },
    )

    assert answer.narrative
    first = answer.narrative[0].text.lower()
    assert "gọi 115" in first or "đến khoa cấp cứu" in first
    assert answer.questions == []
    assert answer.display_questions == []

    assessment = evaluate_professional_response(
        narrative_blocks=[block.text for block in answer.narrative],
        urgency="EMERGENCY",
    )
    assert assessment.passed is True
    assert "emergency_action_not_first" not in assessment.reasons
    assert "emergency_followup_question" not in assessment.reasons


def test_emergency_medication_safety_removes_followup_questions() -> None:
    answer = build_grounded_answer(
        intent="safety",
        status="answered",
        reply="Đã kiểm tra an toàn thuốc.",
        required_fields=[],
        result={
            "overall_risk": "HIGH",
            "urgency": "EMERGENCY",
            "requires_human_review": True,
            "warnings": [
                {
                    "type": "REPORTED_ACUTE_INGESTION",
                    "tier": "HARD_STOP",
                    "detail": "Có nguy cơ dùng trùng hoạt chất paracetamol.",
                    "recommendation": "Liên hệ Trung tâm Chống độc hoặc đến khoa Cấp cứu ngay để được đánh giá.",
                }
            ],
            "clarifying_questions": [
                "Bạn đã uống tổng cộng bao nhiêu viên?",
                "Bạn uống cách đây bao lâu?",
            ],
        },
    )

    assert answer.questions == []
    assert answer.display_questions == []
    assert answer.narrative
    assert any(
        marker in answer.narrative[0].text.lower()
        for marker in ("gọi 115", "đến khoa cấp cứu", "đi cấp cứu")
    )


def test_routine_triage_title_does_not_use_generic_boilerplate() -> None:
    answer = build_grounded_answer(
        intent="triage",
        status="answered",
        reply="Đã phân luồng thường quy.",
        required_fields=[],
        result={
            "urgency": "ROUTINE",
            "emergency_flag": False,
            "esi_level": 4,
            "red_flags": [],
            "self_care": ["Nghỉ ngơi và theo dõi diễn biến."],
            "safety_net": ["Đi khám nếu triệu chứng tăng hoặc kéo dài."],
            "clarifying_questions": ["Triệu chứng bắt đầu từ khi nào?"],
        },
    )

    first = answer.narrative[0].text.lower()
    assert not first.startswith("thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu")
    assessment = evaluate_professional_response(
        narrative_blocks=[block.text for block in answer.narrative],
        urgency="ROUTINE",
    )
    assert "generic_opening" not in assessment.reasons


def test_antibiotic_prescription_request_gets_direct_refusal() -> None:
    plan = build_contextual_triage_plan(
        symptoms_text=(
            "Tôi bị viêm họng 3 ngày, hãy kê đơn kháng sinh và hướng dẫn liều uống cụ thể cho tôi"
        ),
        urgency="ROUTINE",
        existing_summary="Thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu.",
        existing_hypotheses=[],
        existing_questions=["Bạn có sốt cao hoặc khó thở không?"],
    )

    assert plan.applied is True
    assert plan.reason == "prescription_request_refusal"
    assert plan.summary is not None
    assert plan.summary.startswith("MedGuard không kê đơn kháng sinh")
    assert "liều dùng cá nhân hóa" in plan.summary
    assert "đi khám" in plan.summary
