from app.models.chat import GroundedAnswer
from app.services.v27_2_answering_patch import _sanitize_answer


def _answer(**updates) -> GroundedAnswer:
    payload = {
        "title": "Kết quả hiện tại",
        "summary": "Cần đánh giá trực tiếp.",
        "decision_basis": "versioned_rules",
        "evidence_state": "bounded_result",
    }
    payload.update(updates)
    return GroundedAnswer(**payload)


def test_sanitizer_removes_multiline_conversation_transcript_from_key_points() -> None:
    leaked = (
        "Tôi hơi tức cơ ngực sau buổi tập gym tối qua.\n"
        "Hôm nay đi bộ nhanh thì nặng ngực hơn.\n"
        "Bây giờ đau lan tay trái và vã mồ hôi."
    )
    answer = _answer(
        key_points=[
            "Hướng chuyên khoa hiện tại: Tim mạch.",
            leaked,
        ]
    )

    cleaned = _sanitize_answer(answer)

    assert cleaned.key_points == ["Hướng chuyên khoa hiện tại: Tim mạch."]
    assert "tập gym" not in " ".join(cleaned.key_points).lower()


def test_sanitizer_deduplicates_equivalent_red_flag_bullets() -> None:
    answer = _answer(
        key_points=[
            "Dấu hiệu đã được xác nhận từ bệnh cảnh hiện tại: nặng ngực..",
            "Dấu hiệu được nhận diện: nặng ngực",
        ]
    )

    cleaned = _sanitize_answer(answer)

    assert len(cleaned.key_points) == 1
    assert cleaned.key_points[0].endswith("nặng ngực.")
    assert ".." not in cleaned.key_points[0]


def test_sanitizer_preserves_emergency_action_while_cleaning_presentation() -> None:
    emergency = "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức; không tự lái xe."
    answer = _answer(
        summary="Bạn cần cấp cứu ngay..",
        next_steps=[emergency],
        safety_notes=["Không trì hoãn việc đánh giá cấp cứu.."],
    )

    cleaned = _sanitize_answer(answer)

    assert cleaned.next_steps == [emergency]
    assert cleaned.summary == "Bạn cần cấp cứu ngay."
    assert cleaned.safety_notes == ["Không trì hoãn việc đánh giá cấp cứu."]
