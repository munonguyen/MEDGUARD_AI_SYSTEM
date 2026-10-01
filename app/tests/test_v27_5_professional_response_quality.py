from app.models.chat import AnswerNarrativeBlock, GroundedAnswer
from app.services.professional_response_gate import evaluate_professional_response
from app.services.professional_response_quality import (
    apply_professional_response_quality,
    narrative_repetition_ratio,
)


def _answer(**updates: object) -> GroundedAnswer:
    base = GroundedAnswer(
        title="Giải thích triệu chứng hiện tại",
        summary="Triệu chứng hiện tại cần được theo dõi. Triệu chứng hiện tại cần được theo dõi.",
        key_points=["Dữ kiện A", "Dữ kiện B"],
        next_steps=["Theo dõi diễn biến và liên hệ cơ sở y tế nếu triệu chứng tăng."],
        safety_notes=["Đi khám sớm nếu xuất hiện dấu hiệu cảnh báo."],
        questions=["Triệu chứng bắt đầu từ khi nào?"],
        display_questions=["Triệu chứng bắt đầu từ khi nào?"],
        decision_basis="versioned_rules",
        evidence_state="bounded_result",
        limitations=["Không thể khẳng định chẩn đoán chỉ từ hội thoại."],
        narrative=[
            AnswerNarrativeBlock(
                kind="paragraph",
                text="Triệu chứng hiện tại cần được theo dõi. Triệu chứng hiện tại cần được theo dõi.",
                emphasis=["Triệu chứng hiện tại cần được theo dõi"],
                source_ids=["claim-1", "claim-1"],
            ),
            AnswerNarrativeBlock(
                kind="paragraph",
                text="Triệu chứng hiện tại cần được theo dõi.",
                source_ids=["claim-1"],
            ),
            AnswerNarrativeBlock(
                kind="paragraph",
                text="Bạn nên theo dõi diễn biến và ghi nhận thay đổi mới.",
                source_ids=["claim-2"],
            ),
        ],
    )
    return base.model_copy(update=updates)


def test_v27_5_removes_repeated_patient_prose_without_changing_structured_claims() -> None:
    answer = _answer()
    polished = apply_professional_response_quality(
        answer,
        urgency="ROUTINE",
        intent="triage",
    )

    assert polished.summary == "Triệu chứng hiện tại cần được theo dõi."
    assert len(polished.narrative) == 2
    assert narrative_repetition_ratio(polished) == 0.0

    # Clinical authority fields are presentation-pass invariants.
    assert polished.title == answer.title
    assert polished.key_points == answer.key_points
    assert polished.next_steps == answer.next_steps
    assert polished.safety_notes == answer.safety_notes
    assert polished.questions == answer.questions
    assert polished.display_questions == answer.display_questions
    assert polished.limitations == answer.limitations


def test_v27_5_preserves_source_ids_and_filters_stale_emphasis() -> None:
    answer = _answer(
        narrative=[
            AnswerNarrativeBlock(
                text="Đau tăng khi vận động. Đau tăng khi vận động.",
                emphasis=["Đau tăng khi vận động", "không tồn tại"],
                source_ids=["claim-1", "claim-1", "source-2"],
            )
        ]
    )

    polished = apply_professional_response_quality(answer, urgency="ROUTINE", intent="triage")

    assert polished.narrative[0].text == "Đau tăng khi vận động."
    assert polished.narrative[0].emphasis == ["Đau tăng khi vận động"]
    assert polished.narrative[0].source_ids == ["claim-1", "source-2"]


def test_v27_5_merges_provenance_from_duplicate_blocks() -> None:
    answer = _answer(
        narrative=[
            AnswerNarrativeBlock(
                text="Kiểu đau hiện tại phù hợp hơn với đau cơ thành ngực sau vận động.",
                emphasis=["đau cơ thành ngực"],
                source_ids=["claim-1"],
            ),
            AnswerNarrativeBlock(
                text="Kiểu đau hiện tại phù hợp hơn với đau cơ thành ngực sau vận động!",
                emphasis=["sau vận động"],
                source_ids=["source-2", "claim-1"],
            ),
        ]
    )

    polished = apply_professional_response_quality(answer, urgency="ROUTINE", intent="triage")

    assert len(polished.narrative) == 1
    assert polished.narrative[0].source_ids == ["claim-1", "source-2"]
    assert polished.narrative[0].emphasis == ["đau cơ thành ngực", "sau vận động"]


def test_v27_5_emergency_is_completely_untouched() -> None:
    answer = _answer(
        title="Bạn cần được đánh giá cấp cứu ngay",
        summary="Gọi 115 ngay. Gọi 115 ngay.",
        next_steps=["Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay."],
        safety_notes=["Không tự lái xe."],
        questions=[],
        display_questions=[],
        narrative=[
            AnswerNarrativeBlock(kind="urgent", text="Gọi 115 ngay. Gọi 115 ngay."),
            AnswerNarrativeBlock(kind="urgent", text="Gọi 115 ngay."),
        ],
    )
    before = answer.model_dump()

    polished = apply_professional_response_quality(
        answer,
        urgency="EMERGENCY",
        intent="triage",
    )

    assert polished.model_dump() == before


def test_v27_5_near_duplicate_blocks_are_removed_conservatively() -> None:
    answer = _answer(
        narrative=[
            AnswerNarrativeBlock(
                text="Các đặc điểm hiện tại phù hợp hơn với đau cơ thành ngực sau vận động."
            ),
            AnswerNarrativeBlock(
                text="Các đặc điểm hiện tại phù hợp hơn với đau cơ thành ngực sau vận động!"
            ),
            AnswerNarrativeBlock(
                text="Nếu xuất hiện khó thở hoặc đau tăng rõ, bạn cần được đánh giá y tế."
            ),
        ]
    )

    polished = apply_professional_response_quality(answer, urgency="ROUTINE", intent="triage")

    assert len(polished.narrative) == 2
    assert "khó thở" in polished.narrative[-1].text
    assert narrative_repetition_ratio(polished) == 0.0


def test_v27_5_jev_requests_revision_for_repetitive_non_emergency_prose() -> None:
    assessment = evaluate_professional_response(
        narrative_blocks=[
            "Dựa trên thông tin hiện có, kiểu đau này thường phù hợp với căng cơ. Bạn nên nghỉ vận động nặng và theo dõi diễn biến.",
            "Dựa trên thông tin hiện có, kiểu đau này thường phù hợp với căng cơ. Bạn nên nghỉ vận động nặng và theo dõi diễn biến.",
        ],
        urgency="ROUTINE",
    )

    assert not assessment.passed
    assert assessment.decision == "revise"
    assert assessment.professionalism < 1.0
    assert "excessive_repetition" in assessment.reasons


def test_v27_5_jev_does_not_reject_emergency_for_repeated_hard_stop_alone() -> None:
    assessment = evaluate_professional_response(
        narrative_blocks=[
            "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay. Không thể khẳng định nguyên nhân từ xa.",
            "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay.",
        ],
        urgency="EMERGENCY",
    )

    assert "excessive_repetition" not in assessment.reasons
