from app.models.chat import GroundedAnswer
from app.services.clinical_agent_contract import ClinicalAgentContract
from app.services.fallback_response_refinement import refine_contract_fallback


def _answer(**updates: object) -> GroundedAnswer:
    base = GroundedAnswer(
        title="Đặc điểm hiện tại giúp thu hẹp nguyên nhân",
        summary="Đặc điểm liên quan tư thế làm cơ chế cơ học hợp lý hơn.",
        key_points=[
            "Tôi hơi đau lưng do ngồi lâu, đi lại thì giảm.",
            "Hướng chuyên khoa hiện tại: Cơ xương khớp.",
        ],
        next_steps=["Theo dõi diễn biến và đi khám nếu đau tăng."],
        safety_notes=[],
        questions=[],
        display_questions=[],
        decision_basis="versioned_rules",
        evidence_state="bounded_result",
    )
    return base.model_copy(update=updates)


def _contract(*, intent: str, urgency: str = "ROUTINE", question: str = "") -> ClinicalAgentContract:
    return ClinicalAgentContract(
        envelope={
            "intent": intent,
            "user_question": question,
            "clinical_result": {
                "urgency": urgency,
                "conversation_turn": question,
            },
            "safety_constraints": {"urgency_floor": urgency},
        },
        claims=[],
    )


def test_triage_fallback_promotes_existing_patient_fact_without_mutating_claim_fields() -> None:
    answer = _answer()
    before = answer.model_dump()

    refined = refine_contract_fallback(
        answer,
        _contract(intent="triage", question="Tôi hơi đau lưng do ngồi lâu, đi lại thì giảm."),
    )

    assert refined.summary.startswith("Bạn hơi đau lưng do ngồi lâu, đi lại thì giảm.")
    assert refined.key_points == answer.key_points
    assert refined.next_steps == answer.next_steps
    assert refined.safety_notes == answer.safety_notes
    assert refined.questions == answer.questions
    assert refined.model_dump(exclude={"summary"}) == {
        key: value for key, value in before.items() if key != "summary"
    }


def test_medication_action_question_promotes_only_an_existing_approved_action() -> None:
    approved = (
        "Không tự bắt đầu, ngừng hoặc phối hợp thuốc trước khi trao đổi với bác sĩ hoặc dược sĩ."
    )
    answer = _answer(
        title="Có cảnh báo an toàn thuốc cần ưu tiên xử lý",
        summary="Bạn đang dùng warfarin và aspirin và đang cân nhắc ibuprofen.",
        key_points=["warfarin + aspirin: tăng nguy cơ chảy máu."],
        next_steps=[approved, "Hỏi bác sĩ hoặc dược sĩ về lựa chọn thay thế phù hợp."],
    )

    refined = refine_contract_fallback(
        answer,
        _contract(
            intent="safety",
            question="Nếu tôi chưa uống ibuprofen thì bước an toàn nhất bây giờ là gì?",
        ),
    )

    assert refined.summary.startswith(approved)
    assert refined.next_steps == answer.next_steps
    assert "ibuprofen" in refined.summary


def test_emergency_fallback_is_byte_for_byte_unchanged() -> None:
    answer = _answer(
        title="Bạn cần được đánh giá cấp cứu ngay",
        summary="Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay.",
        next_steps=["Gọi 115 ngay."],
    )
    before = answer.model_dump()

    refined = refine_contract_fallback(
        answer,
        _contract(
            intent="triage",
            urgency="EMERGENCY",
            question="Tôi đau ngực lan tay trái và vã mồ hôi.",
        ),
    )

    assert refined.model_dump() == before
