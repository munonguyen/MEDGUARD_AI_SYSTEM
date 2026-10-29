from app.services.answering import _triage_answer


def test_unresolved_triage_does_not_claim_routine_or_recommend_home_monitoring():
    answer = _triage_answer({"urgency": "UNRESOLVED", "clarifying_questions": ["Bạn muốn hỏi về vấn đề gì?"]}, [])
    assert "chưa đủ thông tin" in answer.summary
    assert "thường quy" not in answer.summary
    assert answer.next_steps == []
    assert answer.questions == ["Bạn muốn hỏi về vấn đề gì?"]
