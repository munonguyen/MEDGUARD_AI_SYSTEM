from app.services import answering
from app.services.clinical_agent_contract import build_clinical_agent_contract
from app.services.clinical_contract_fallback import compose_contract_fallback


def _fallback_summary(question: str) -> str:
    result = {
        "urgency": "ROUTINE",
        "matched": True,
        "red_flags": [],
        "conversation_turn": question,
        "clarifying_questions": ["Triệu chứng đang tăng, giảm hay giữ nguyên?"],
    }
    base = answering.build_grounded_answer(
        intent="triage",
        status="answered",
        reply="unused",
        required_fields=[],
        result=result,
    )
    contract = build_clinical_agent_contract(
        intent="triage",
        question=question,
        clinical_result=result,
    )
    return compose_contract_fallback(base, contract).summary


def test_generic_triage_fallback_is_grounded_in_current_turn() -> None:
    summary = _fallback_summary("Tôi bị dao cắt vào ngón tay, vết khoảng 1 cm.")
    assert "dao cắt" in summary.lower()
    assert "1 cm" in summary.lower()


def test_unrelated_routine_complaints_do_not_collapse_to_identical_summary() -> None:
    abdominal = _fallback_summary("Tôi đau âm ỉ quanh rốn từ sáng nay.")
    eye = _fallback_summary("Mắt trái của tôi đỏ và hơi cộm từ sáng.")
    assert abdominal != eye
