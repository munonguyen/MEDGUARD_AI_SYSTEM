from __future__ import annotations

from app.services.professional_response_gate import evaluate_professional_response


def test_routine_direct_actionable_response_passes() -> None:
    result = evaluate_professional_response(
        narrative_blocks=[
            "Đau lưng sau khi ngồi lâu thường phù hợp với căng cơ hơn là một tình trạng cấp cứu nếu không có yếu chân, tê vùng yên ngựa hoặc rối loạn tiểu tiện.",
            "Bạn nên đứng dậy đi lại nhẹ, đổi tư thế và theo dõi; nếu đau tăng, kéo dài hoặc xuất hiện yếu/tê chân thì đi khám.",
        ],
        urgency="ROUTINE",
    )

    assert result.passed is True
    assert result.score >= 0.85
    assert result.reasons == ()


def test_generic_boilerplate_opening_is_rejected() -> None:
    result = evaluate_professional_response(
        narrative_blocks=[
            "Thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu. Cần thêm đánh giá lâm sàng toàn diện.",
            "Bạn nên theo dõi triệu chứng.",
        ],
        urgency="ROUTINE",
    )

    assert result.passed is False
    assert "generic_opening" in result.reasons


def test_emergency_requires_action_in_opening_and_no_question() -> None:
    result = evaluate_professional_response(
        narrative_blocks=[
            "Tình trạng này có thể nguy hiểm. Bạn đang khó thở phải không?",
            "Nếu nặng hơn thì đi cấp cứu.",
        ],
        urgency="EMERGENCY",
    )

    assert result.passed is False
    assert "emergency_action_not_first" in result.reasons
    assert "emergency_followup_question" in result.reasons


def test_emergency_immediate_action_passes_when_locked_claim_is_preserved() -> None:
    locked = "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức; không tự lái xe và không trì hoãn để tiếp tục hỏi trực tuyến."
    result = evaluate_professional_response(
        narrative_blocks=[
            locked,
            "Khó thở kèm đau ngực cần được đánh giá ngay vì có thể liên quan đến tim hoặc phổi.",
        ],
        urgency="EMERGENCY",
        locked_claims=[locked],
    )

    assert result.passed is True
    assert result.safety == 1.0


def test_internal_agent_jargon_is_not_patient_facing() -> None:
    result = evaluate_professional_response(
        narrative_blocks=[
            "Safety Kernel đã đặt routing decision ở mức URGENT.",
            "Bạn nên đi khám trong hôm nay.",
        ],
        urgency="URGENT",
    )

    assert result.passed is False
    assert "internal_jargon_leak" in result.reasons


def test_false_reassurance_is_hard_failure() -> None:
    result = evaluate_professional_response(
        narrative_blocks=[
            "Tình trạng này chắc chắn không nguy hiểm.",
            "Bạn nên theo dõi tại nhà.",
        ],
        urgency="ROUTINE",
    )

    assert result.passed is False
    assert result.safety == 0.0
    assert "false_reassurance" in result.reasons


def test_missing_locked_safety_action_is_rejected() -> None:
    result = evaluate_professional_response(
        narrative_blocks=["Bạn nên đi cấp cứu ngay."],
        urgency="EMERGENCY",
        locked_claims=["Không tự lái xe."],
    )

    assert result.passed is False
    assert "missing_locked_claim" in result.reasons
