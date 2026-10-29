from app.services.clinical_agent_contract import build_clinical_agent_contract
from app.services.clinical_episode_model import build_clinical_episode_model


def _user(*messages: str):
    return [{"role": "user", "content": value} for value in messages]


def test_unmentioned_findings_remain_unknown_not_negative():
    episode = build_clinical_episode_model(
        episode_id="v25-headache-unknown",
        messages=_user("Tôi đau đầu nhẹ sau khi nhìn màn hình cả ngày."),
    )

    assert episode.chief_domain == "neurovestibular"
    assert episode.confirmed_negative == ()
    unknown_keys = {item.key for item in episode.unknown_decision_relevant}
    assert "onset_speed" in unknown_keys
    assert "focal_neurologic_deficit" in unknown_keys
    assert "fever_neck_stiffness" in unknown_keys


def test_question_five_style_case_gets_mechanism_and_high_information_question():
    contract = build_clinical_agent_contract(
        intent="triage",
        question="Tôi đau đầu nhẹ sau khi nhìn màn hình cả ngày.",
        clinical_result={"urgency": "ROUTINE", "red_flags": []},
    )

    episode = contract.envelope["clinical_episode"]
    frame = contract.envelope["reasoning_frame"]
    assert episode is not None
    assert frame is not None
    ids = {item["hypothesis_id"] for item in frame["mechanisms"]}
    assert "visual_load_contribution" in ids
    assert "postural_pericranial_tension" in ids
    assert frame["next_question_key"] == "onset_speed"
    assert "đột ngột" in frame["next_best_question"].lower()

    mechanism_claims = [claim for claim in contract.claims if claim["category"] == "mechanism"]
    question_claims = [claim for claim in contract.claims if claim["category"] == "question"]
    assert mechanism_claims
    assert len(question_claims) == 1


def test_followup_turn_preserves_previous_trigger_and_updates_unknowns():
    contract = build_clinical_agent_contract(
        intent="triage",
        question=(
            "Tôi đau đầu nhẹ sau khi nhìn màn hình cả ngày.\n"
            "Lượt hiện tại: Đau chủ yếu vùng trán, không sốt, nghỉ một lúc thì giảm."
        ),
        clinical_result={"urgency": "ROUTINE", "red_flags": []},
    )

    episode = contract.envelope["clinical_episode"]
    frame = contract.envelope["reasoning_frame"]
    assert episode is not None and frame is not None
    assert "nhìn màn hình" in episode["active_episode_text"].lower()
    ids = {item["hypothesis_id"] for item in frame["mechanisms"]}
    assert "visual_load_contribution" in ids
    unknown_keys = {item["key"] for item in episode["unknown_decision_relevant"]}
    assert "fever_neck_stiffness" not in unknown_keys
    assert frame["next_question_key"] == "onset_speed"


def test_emergency_contract_never_asks_contextual_followup_before_action():
    contract = build_clinical_agent_contract(
        intent="triage",
        question="Vừa rồi tôi đột ngột đau đầu dữ dội nhất từ trước tới giờ.",
        clinical_result={"urgency": "EMERGENCY", "red_flags": ["thunderclap_headache"]},
    )

    frame = contract.envelope["reasoning_frame"]
    assert frame is not None
    assert frame["next_best_question"] is None
    assert not [claim for claim in contract.claims if claim["category"] == "question"]
    locked_actions = [
        claim for claim in contract.claims
        if claim["category"] == "action" and claim["locked"]
    ]
    assert len(locked_actions) == 1
    assert "115" in locked_actions[0]["text"]


def test_explicitly_answered_red_flag_slot_is_not_reasked():
    episode = build_clinical_episode_model(
        episode_id="v25-headache-negative",
        messages=_user("Tôi đau đầu tăng từ từ, không sốt và không cứng gáy."),
    )

    unknown_keys = {item.key for item in episode.unknown_decision_relevant}
    assert "onset_speed" not in unknown_keys
    assert "fever_neck_stiffness" not in unknown_keys


def test_clear_new_complaint_resets_active_episode_context():
    episode = build_clinical_episode_model(
        episode_id="v25-switch",
        messages=_user(
            "Tôi đau đầu nhẹ sau khi học lâu.",
            "Vấn đề mới không liên quan: tôi đau bụng dưới bên phải.",
        ),
    )

    assert episode.delta.episode_switched is True
    assert episode.user_turns_in_active_episode == 1
    assert episode.chief_domain == "gastrointestinal"


def test_emergency_history_is_exposed_as_historical_risk_after_partial_relief():
    episode = build_clinical_episode_model(
        episode_id="v25-risk-memory",
        messages=_user(
            "Bây giờ miệng tôi méo, tay phải yếu và nói ngọng đột ngột.",
            "Nói đã rõ hơn một chút nhưng tay vẫn yếu, tôi thấy đỡ hơn rồi.",
        ),
    )

    # Exact parser concept names may evolve, but a hard prior event must stay
    # visible to the episode model rather than disappearing after improvement.
    assert episode.has_hard_historical_risk is True
    assert episode.historical_risk
    assert all(fact.source_turn < 2 for fact in episode.historical_risk)
