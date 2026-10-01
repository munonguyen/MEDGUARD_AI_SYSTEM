from app.services.clinical_agent_contract import build_clinical_agent_contract


def _mechanisms(contract):
    return contract.envelope["reasoning_frame"]["mechanisms"]


def test_post_gym_reproducible_chest_pain_keeps_mechanical_explanation_leading():
    contract = build_clinical_agent_contract(
        intent="triage",
        question="Tôi hơi tức cơ ngực sau buổi tập gym tối qua, ấn vào thì đau hơn.",
        clinical_result={"urgency": "ROUTINE", "red_flags": []},
    )

    frame = contract.envelope["reasoning_frame"]
    assert frame is not None
    assert frame["leading_hypothesis_ids"] == ["chest_wall_mechanical"]
    assert _mechanisms(contract)[0]["hypothesis_id"] == "chest_wall_mechanical"


def test_new_exertional_chest_pressure_replaces_old_chest_wall_hypothesis_as_leading():
    contract = build_clinical_agent_contract(
        intent="triage",
        question=(
            "Tôi hơi tức cơ ngực sau buổi tập gym tối qua, ấn vào thì đau hơn.\n"
            "Lượt hiện tại: Hôm nay đi bộ nhanh thì cảm giác nặng ngực rõ hơn và hơi hụt hơi."
        ),
        clinical_result={"urgency": "URGENT", "red_flags": []},
    )

    frame = contract.envelope["reasoning_frame"]
    assert frame is not None
    assert frame["leading_hypothesis_ids"] == ["episode_delta_cardiorespiratory_warning"]
    by_id = {item["hypothesis_id"]: item for item in frame["mechanisms"]}
    assert by_id["episode_delta_cardiorespiratory_warning"]["role"] == "leading"
    assert by_id["chest_wall_mechanical"]["role"] == "contributor"
    assert "gắng sức" in by_id["episode_delta_cardiorespiratory_warning"]["mechanism"].lower()

    explanation = contract.envelope["explanation_frame"]
    assert explanation["what_it_may_mean"] == by_id["episode_delta_cardiorespiratory_warning"]["patient_safe_statement"]
    assert "tim–phổi" in explanation["what_it_may_mean"]


def test_autonomic_radiating_chest_pain_becomes_emergency_leading_explanation():
    contract = build_clinical_agent_contract(
        intent="triage",
        question=(
            "Tôi hơi tức cơ ngực sau buổi tập gym tối qua, ấn vào thì đau hơn.\n"
            "Lượt hiện tại: Bây giờ đau lan xuống tay trái, vã mồ hôi và buồn nôn."
        ),
        clinical_result={
            "urgency": "EMERGENCY",
            "emergency_flag": True,
            "red_flags": ["chest_pain_radiation_autonomic"],
        },
    )

    frame = contract.envelope["reasoning_frame"]
    assert frame is not None
    assert frame["leading_hypothesis_ids"] == ["episode_delta_cardiorespiratory_warning"]
    assert frame["next_best_question"] is None

    explanation = contract.envelope["explanation_frame"]
    text = f"{explanation['what_it_may_mean']} {explanation['mechanism']}".lower()
    assert "tim–phổi" in text
    assert "vã mồ hôi" in text
    assert "cấp cứu" in text

    question_claims = [claim for claim in contract.claims if claim["category"] == "question"]
    assert question_claims == []


def test_transient_improvement_does_not_restore_benign_chest_wall_explanation_after_emergency():
    contract = build_clinical_agent_contract(
        intent="triage",
        question=(
            "Tôi hơi tức cơ ngực sau buổi tập gym tối qua, ấn vào thì đau hơn.\n"
            "Hôm nay đi bộ nhanh thì cảm giác nặng ngực rõ hơn và hơi hụt hơi.\n"
            "Bây giờ đau lan xuống tay trái, vã mồ hôi và buồn nôn.\n"
            "Lượt hiện tại: Tôi ngồi nghỉ 10 phút thấy đỡ nhiều rồi, vậy chắc không cần cấp cứu nữa đúng không?"
        ),
        clinical_result={
            "urgency": "EMERGENCY",
            "emergency_flag": True,
            "red_flags": ["historical_chest_pain_radiation_autonomic"],
        },
    )

    frame = contract.envelope["reasoning_frame"]
    assert frame is not None
    assert frame["leading_hypothesis_ids"] == ["historical_cardiorespiratory_emergency"]
    assert frame["next_best_question"] is None

    by_id = {item["hypothesis_id"]: item for item in frame["mechanisms"]}
    historical = by_id["historical_cardiorespiratory_emergency"]
    assert historical["role"] == "leading"
    assert "tạm" in historical["patient_safe_statement"].lower()
    assert "hạ mức cấp cứu" in historical["patient_safe_statement"].lower()
    if "chest_wall_mechanical" in by_id:
        assert by_id["chest_wall_mechanical"]["role"] == "contributor"

    explanation = contract.envelope["explanation_frame"]
    visible_explanation = f"{explanation['what_it_may_mean']} {explanation['mechanism']}".lower()
    assert "không xóa" in visible_explanation
    assert "đau lan" in visible_explanation
    assert "cấp cứu" in visible_explanation

    question_claims = [claim for claim in contract.claims if claim["category"] == "question"]
    assert question_claims == []
