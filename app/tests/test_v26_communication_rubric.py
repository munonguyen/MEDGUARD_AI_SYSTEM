from __future__ import annotations

from app.services.jury_evaluator import CommunicationQualityEvaluator, SafetyGateResult


_SAFE = SafetyGateResult(passed=True)


def test_vietnamese_imperatives_are_recognized_as_actionable() -> None:
    assessment = CommunicationQualityEvaluator.evaluate(
        question="Tôi nên làm gì tiếp theo?",
        answer_text=(
            "Hãy cung cấp các lần đo tiếp theo cùng đơn vị và đo lại sau khi nghỉ. "
            "Nếu chỉ số xấu đi, nên liên hệ cơ sở y tế."
        ),
        high_risk=False,
        safety_gate=_SAFE,
        groundedness=1.0,
    )

    assert assessment.dimensions["actionability"].score == 4
    assert assessment.score >= 0.80
    assert "Hành động cụ thể tiếp theo" not in assessment.missing_critical_items


def test_self_contained_how_to_question_does_not_require_an_extra_followup() -> None:
    assessment = CommunicationQualityEvaluator.evaluate(
        question="Chỉ tôi cách đo huyết áp tại nhà cho đúng.",
        answer_text=(
            "Hãy ngồi nghỉ trước khi đo, đặt cánh tay ngang mức tim và đo lại theo hướng dẫn của thiết bị. "
            "Ghi lại kết quả và đơn vị để theo dõi."
        ),
        high_risk=False,
        safety_gate=_SAFE,
        groundedness=1.0,
    )

    assert assessment.dimensions["context_seeking"].score == 4
    assert assessment.score >= 0.80
    assert "Câu hỏi làm rõ dữ kiện có thể thay đổi khuyến nghị" not in assessment.missing_critical_items
