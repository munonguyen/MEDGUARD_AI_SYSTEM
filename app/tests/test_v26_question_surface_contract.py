from __future__ import annotations

from app.models.chat import AnswerNarrativeBlock, ChatResponse, GroundedAnswer


def _triage_answer() -> GroundedAnswer:
    return GroundedAnswer(
        title="Bạn nên được nhân viên y tế đánh giá sớm",
        summary="Triệu chứng cần được đánh giá trực tiếp sớm.",
        next_steps=["Hãy sắp xếp đi khám trực tiếp sớm."],
        questions=[
            "Triệu chứng bắt đầu từ khi nào?",
            "Mức độ đau hiện tại là bao nhiêu?",
            "Bạn có sốt không?",
        ],
        narrative=[
            AnswerNarrativeBlock(
                text="Bạn nên được nhân viên y tế đánh giá sớm."
            ),
            AnswerNarrativeBlock(
                text=(
                    "Bạn cho mình biết thêm: Triệu chứng bắt đầu từ khi nào? "
                    "Mức độ đau hiện tại là bao nhiêu? Bạn có sốt không?"
                ),
                emphasis=["Bạn cho mình biết thêm"],
            ),
        ],
        decision_basis="versioned_rules",
        evidence_state="bounded_result",
        requires_human_review=True,
    )


def test_triage_question_policy_preserves_candidates_and_limits_patient_surface() -> None:
    response = ChatResponse(
        request_id="v26-question-surface",
        conversation_id="v26-question-surface",
        status="answered",
        intent="triage",
        reply="Đã đánh giá.",
        result={"urgency": "URGENT", "trace": {"details": {}}},
        answer=_triage_answer(),
    )

    assert response.answer is not None
    # Full approved candidates remain available for audit/evaluation.
    assert len(response.answer.questions) == 3
    # The patient surface follows the deterministic dialogue policy: ROUTINE <=1,
    # URGENT <=2, while EMERGENCY is handled separately below with zero questions.
    assert response.answer.display_questions is not None
    assert len(response.answer.display_questions) <= 2
    assert set(response.answer.display_questions).issubset(set(response.answer.questions))

    rendered = " ".join(block.text for block in response.answer.narrative)
    assert rendered.count("?") <= len(response.answer.display_questions)
    for question in response.answer.display_questions:
        assert question in rendered


def test_emergency_surface_removes_all_followup_questions() -> None:
    answer = _triage_answer().model_copy(
        update={
            "title": "Bạn cần được đánh giá cấp cứu ngay",
            "next_steps": ["Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức."],
        }
    )
    response = ChatResponse(
        request_id="v26-zero-question",
        conversation_id="v26-zero-question",
        status="answered",
        intent="triage",
        reply="Cần cấp cứu.",
        result={"urgency": "EMERGENCY", "trace": {"details": {}}},
        answer=answer,
    )

    assert response.answer is not None
    assert response.answer.questions == []
    assert response.answer.display_questions == []
    assert all(
        not block.text.startswith("Bạn cho mình biết thêm")
        for block in response.answer.narrative
    )
