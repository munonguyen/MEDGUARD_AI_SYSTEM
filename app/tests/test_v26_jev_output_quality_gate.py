from __future__ import annotations

from app.services.professional_response_gate import evaluate_jev_release


def test_jev_release_approves_actionable_bounded_clinical_response() -> None:
    assessment = evaluate_jev_release(
        narrative_blocks=[
            "Bạn nên sắp xếp khám trực tiếp sớm vì triệu chứng vẫn đang tiến triển.",
            "Không thể xác định nguyên nhân chỉ từ tin nhắn; nếu khó thở tăng hoặc choáng, hãy đến cơ sở cấp cứu.",
        ],
        urgency="URGENT",
    )

    assert assessment.passed is True
    assert assessment.decision == "approve"
    assert assessment.actionability == 1.0
    assert assessment.calibrated_uncertainty == 1.0


def test_jev_release_requests_revision_when_clinical_answer_has_no_action() -> None:
    assessment = evaluate_jev_release(
        narrative_blocks=[
            "Các triệu chứng này có thể liên quan nhiều nguyên nhân và không thể xác định chỉ từ tin nhắn."
        ],
        urgency="URGENT",
    )

    assert assessment.passed is False
    assert assessment.decision == "revise"
    assert "missing_action" in assessment.reasons


def test_jev_release_rejects_emergency_question_before_release() -> None:
    assessment = evaluate_jev_release(
        narrative_blocks=[
            "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức.",
            "Bạn có thể cho biết thêm cơn đau bắt đầu từ khi nào?",
        ],
        urgency="EMERGENCY",
    )

    assert assessment.passed is False
    assert assessment.decision == "revise"
    assert assessment.question_policy == 0.0
    assert "emergency_followup_question" in assessment.reasons


def test_jev_release_never_changes_supplied_clinical_urgency() -> None:
    assessment = evaluate_jev_release(
        narrative_blocks=[
            "Bạn nên tiếp tục theo dõi triệu chứng và sắp xếp khám nếu không cải thiện.",
            "Với thông tin hiện có, chưa thể xác định nguyên nhân chỉ từ tin nhắn.",
        ],
        urgency="ROUTINE",
    )

    assert assessment.decision in {"approve", "revise"}
    assert not hasattr(assessment, "urgency")
    assert not hasattr(assessment, "triage_recommendation")
