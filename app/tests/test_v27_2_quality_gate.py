from scripts.eval_v27_2_conversation_quality import (
    _norm,
    _output_hygiene_violations,
    _relevance_violations,
)


def _row(question: str, reply: str, category: str = "triage") -> dict[str, object]:
    return {
        "conversation_id": "V24-T0",
        "title": "quality-gate-test",
        "category": category,
        "question_no": 1,
        "turn": 1,
        "question": question,
        "reply": reply,
        "answer_title": "",
        "summary": reply,
        "key_points_raw": "",
        "key_points": [],
        "next_steps_raw": "",
        "safety_notes_raw": "",
        "questions_raw": "",
        "limitations_raw": "",
    }


def test_quality_gate_normalization_removes_vietnamese_diacritics() -> None:
    assert _norm("Huyết áp đột ngột dữ dội") == "huyet ap dot ngot du doi"


def test_quality_gate_detects_monitoring_leak_with_accented_vietnamese() -> None:
    issues = _relevance_violations(
        _row(
            "Huyết áp hiện tại của tôi là 150/95.",
            "Mỏi thị giác do nhìn màn hình có thể gây khó chịu.",
            category="cross_intent_context_switch",
        )
    )
    assert "monitoring_value_not_reflected" in issues
    assert "cross_intent_headache_leak" in issues


def test_quality_gate_detects_stale_headache_hypothesis_with_accents() -> None:
    issues = _relevance_violations(
        _row(
            "Vừa rồi tôi đột ngột đau đầu dữ dội nhất từ trước tới giờ.",
            "Nhìn màn hình làm mỏi thị giác nên bạn có thể nghỉ ngơi.",
        )
    )
    assert "stale_benign_headache_hypothesis" in issues


def test_quality_gate_detects_stale_spine_hypothesis_with_accents() -> None:
    issues = _relevance_violations(
        _row(
            "Tôi khó nhấc bàn chân và khó kiểm soát tiểu tiện.",
            "Nguyên nhân cơ học hợp lý hơn trong trường hợp này.",
        )
    )
    assert "stale_mechanical_spine_hypothesis" in issues


def test_quality_gate_checks_medication_multiturn_category_name() -> None:
    issues = _relevance_violations(
        _row(
            "Tôi đang dùng warfarin, có thể uống thêm ibuprofen không?",
            "Cần kiểm tra thêm trước khi phối hợp thuốc.",
            category="medication_safety_multiturn",
        )
    )
    assert "medication_not_reflected" in issues


def test_quality_gate_detects_transcript_leak_and_multiline_key_point() -> None:
    first = "Tôi hơi tức cơ ngực sau buổi tập gym tối qua."
    current = "Bây giờ đau lan xuống tay trái, vã mồ hôi và buồn nôn."
    row = _row(current, "Bạn cần được đánh giá cấp cứu ngay.")
    row["key_points_raw"] = f"- {first}\n{current}"
    row["key_points"] = [f"{first}\n{current}"]

    issues = _output_hygiene_violations(
        row,
        conversation_questions=[first, current],
    )
    assert "multiline_key_point" in issues
    assert "conversation_transcript_leaked_into_key_points" in issues


def test_quality_gate_detects_duplicate_semantic_findings_and_punctuation() -> None:
    row = _row("Tôi đau ngực.", "Cần đánh giá trực tiếp.")
    row["key_points_raw"] = (
        "- Dấu hiệu đã được xác nhận từ bệnh cảnh hiện tại: nặng ngực..\n"
        "- Dấu hiệu được nhận diện: nặng ngực"
    )
    row["key_points"] = [
        "Dấu hiệu đã được xác nhận từ bệnh cảnh hiện tại: nặng ngực..",
        "Dấu hiệu được nhận diện: nặng ngực",
    ]

    issues = _output_hygiene_violations(row, conversation_questions=[row["question"]])
    assert "duplicate_terminal_punctuation" in issues
    assert "duplicate_semantic_key_point" in issues
