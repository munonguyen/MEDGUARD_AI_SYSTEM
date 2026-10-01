from app.models.chat import AnswerNarrativeBlock, ChatResponse, GroundedAnswer
from app.services.patient_response_surface import canonical_patient_response_text
from app.services.v27_runtime_patch import _install_canonical_reply_surface


def _answer() -> GroundedAnswer:
    return GroundedAnswer(
        title="Đánh giá hiện tại",
        summary="Tóm tắt tương thích cũ.",
        key_points=["Dữ kiện đã xác nhận"],
        next_steps=["Theo dõi diễn biến."],
        safety_notes=["Đi khám nếu triệu chứng tăng."],
        questions=["Triệu chứng bắt đầu từ khi nào?"],
        display_questions=["Triệu chứng bắt đầu từ khi nào?"],
        decision_basis="versioned_rules",
        evidence_state="bounded_result",
        limitations=["Không thay thế thăm khám trực tiếp."],
        narrative=[
            AnswerNarrativeBlock(
                text="Writer verified narrative thứ nhất.",
                source_ids=["claim-1"],
            ),
            AnswerNarrativeBlock(
                text="Bạn cho mình biết thêm: legacy question must stay out of canonical context?",
            ),
            AnswerNarrativeBlock(
                text="Writer verified narrative thứ hai.",
                source_ids=["claim-2"],
            ),
        ],
    )


def test_verified_surface_uses_visible_writer_narrative() -> None:
    text = canonical_patient_response_text(
        answer=_answer(),
        verification_status="verified",
        fallback_text="transport summary",
    )

    assert text == (
        "Writer verified narrative thứ nhất.\n\n"
        "Writer verified narrative thứ hai."
    )
    assert "legacy question" not in text
    assert "transport summary" not in text


def test_non_verified_surface_preserves_deterministic_fallback() -> None:
    text = canonical_patient_response_text(
        answer=_answer(),
        verification_status="rejected",
        fallback_text="deterministic safe fallback",
    )

    assert text == "deterministic safe fallback"


def test_chat_response_reply_is_canonical_only_after_verified_gateway_release() -> None:
    _install_canonical_reply_surface()

    verified = ChatResponse(
        request_id="req-v275-verified",
        conversation_id="conv-v275",
        status="answered",
        intent="triage",
        reply="old summary transport text",
        result={"urgency": "ROUTINE"},
        answer=_answer(),
        answer_origin="gateway_verified",
        verification_status="verified",
        orchestrator="agent_verified",
    )
    rejected = ChatResponse(
        request_id="req-v275-rejected",
        conversation_id="conv-v275",
        status="answered",
        intent="triage",
        reply="deterministic safe fallback",
        result={"urgency": "ROUTINE"},
        answer=_answer(),
        answer_origin="deterministic_fallback",
        verification_status="rejected",
        orchestrator="deterministic_fallback",
    )

    assert verified.reply == (
        "Writer verified narrative thứ nhất.\n\n"
        "Writer verified narrative thứ hai."
    )
    assert rejected.reply == "deterministic safe fallback"
