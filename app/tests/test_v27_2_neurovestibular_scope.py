from app.services.clinical_agent_contract import build_clinical_agent_contract


def _reasoning_text(question: str) -> str:
    contract = build_clinical_agent_contract(
        intent="triage",
        question=question,
        clinical_result={
            "urgency": "ROUTINE",
            "matched": True,
            "red_flags": [],
            "clarifying_questions": [],
        },
    )
    frame = contract.envelope.get("reasoning_frame") or {}
    return str(frame).lower()


def test_dizziness_episode_does_not_inherit_headache_screen_strain_pathway() -> None:
    text = _reasoning_text("Sáng nay tôi hơi choáng khi đứng lên nhanh.")
    assert "secondary_headache_safety_pathway" not in text
    assert "visual_load_contribution" not in text
    assert "mỏi thị giác" not in text


def test_headache_episode_keeps_headache_reasoning_available() -> None:
    text = _reasoning_text("Tôi đau đầu vùng trán sau khi nhìn màn hình nhiều giờ.")
    assert "visual_load_contribution" in text
