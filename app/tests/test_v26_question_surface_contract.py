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


def test_triage_question_policy_is_consistent_on_all_patient_surfaces() -> None:
    response = ChatResponse(
        request_id="v26-one-question",
        conversation_id="v26-one-question",
        status="answered",
        intent="triage",
        reply="Đã đánh giá.",
        result={"urgency": "URGENT", "trace": {"details": {}}},
        answer=_triage_answer(),
    )

    assert response.answer is not None
    assert len(response.answer.questions) <= 1
    assert response.answer.questions == response.answer.display_questions

    rendered = " ".join(block.text for block in response.answer.narrative)
    assert rendered.count("?") <= 1
    if response.answer.questions:
        assert response.answer.questions[0] in rendered


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
