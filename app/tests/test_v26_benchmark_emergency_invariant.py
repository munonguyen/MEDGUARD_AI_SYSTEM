from __future__ import annotations

from scripts.evaluate_v24_200_turn_conversations import TurnSpec, _score_turn


def test_resolved_emergency_never_loses_points_for_zero_followup_questions() -> None:
    spec = TurnSpec(
        question="Triệu chứng đang tăng, tôi nên làm gì?",
        expected_intents={"triage"},
        min_urgency="URGENT",
        expect_followup_question=True,
    )
    body = {
        "intent": "triage",
        "status": "answered",
        "reply": "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức.",
        "result": {"urgency": "EMERGENCY"},
        "answer": {
            "title": "Bạn cần được đánh giá cấp cứu ngay",
            "summary": "Không thể xác định nguyên nhân chỉ từ tin nhắn.",
            "next_steps": ["Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức."],
            "questions": [],
            "display_questions": [],
        },
    }

    evaluation = _score_turn(
        spec,
        body,
        10.0,
        snapshot=[],
        previous_snapshot=[],
        category="triage_multiturn",
    )

    assert evaluation["dimensions"]["question_policy"] == 10
    assert "FOLLOWUP_QUESTION_MISSING" not in evaluation["flags"]
    assert "EMERGENCY_ASKED_FOLLOWUP_BEFORE_ACTION" not in evaluation["flags"]
