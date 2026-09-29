from app.services.clinical_episode_model import build_clinical_episode_model
from app.services.contextual_clinical_reasoner import build_contextual_reasoning_frame
from app.services.risk_memory import infer_episode_domain


def test_hand_joint_pain_routes_to_peripheral_joint_not_spine() -> None:
    text = "Tôi đang cảm thấy đau các khớp tay"
    assert infer_episode_domain(text) == "peripheral_joint"

    episode = build_clinical_episode_model(
        episode_id="v27-hand-joints",
        messages=[{"role": "user", "content": text}],
    )
    assert episode.chief_domain == "peripheral_joint"

    keys = {item.key for item in episode.unknown_decision_relevant}
    assert "joint_inflammatory_signs" in keys
    assert "joint_distribution" in keys
    assert "joint_systemic_features" in keys
    assert "hand_neurovascular_deficit" in keys
    assert "cauda_equina_features" not in keys
    assert "motor_sensory_deficit" not in keys


def test_hand_joint_pain_selects_joint_specific_high_information_question() -> None:
    episode = build_clinical_episode_model(
        episode_id="v27-hand-joints-question",
        messages=[{"role": "user", "content": "Tôi đau các khớp tay khoảng hai ngày nay"}],
    )
    frame = build_contextual_reasoning_frame(episode, urgency="ROUTINE")

    assert frame.next_question_key == "joint_inflammatory_signs"
    assert frame.next_best_question is not None
    question = frame.next_best_question.lower()
    assert "sưng" in question
    assert "nóng" in question
    assert "đỏ" in question
    assert "buổi sáng" in question

    unresolved = {
        key
        for hypothesis in frame.mechanisms
        for key in hypothesis.unresolved
    }
    assert "cauda_equina_features" not in unresolved
    assert "motor_sensory_deficit" not in unresolved


def test_joint_inflammatory_features_change_reasoning_path() -> None:
    episode = build_clinical_episode_model(
        episode_id="v27-inflammatory-joints",
        messages=[
            {
                "role": "user",
                "content": "Tôi đau nhiều khớp tay, buổi sáng khớp bị cứng và hơi sưng nóng đỏ",
            }
        ],
    )
    frame = build_contextual_reasoning_frame(episode, urgency="ROUTINE")

    ids = {item.hypothesis_id for item in frame.mechanisms}
    assert "peripheral_joint_inflammatory_pattern" in ids
    assert frame.next_question_key != "joint_inflammatory_signs"
