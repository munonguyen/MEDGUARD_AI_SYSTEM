from scripts.eval_v27_2_conversation_quality import _norm, _relevance_violations


def _row(question: str, reply: str, category: str = "triage") -> dict[str, object]:
    return {
        "conversation_id": "V24-T0",
        "title": "quality-gate-test",
        "category": category,
        "question_no": 1,
        "turn": 1,
        "question": question,
        "reply": reply,
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
