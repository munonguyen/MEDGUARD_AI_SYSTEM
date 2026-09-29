from app.knowledge.loader import knowledge


def test_headache_guidance_receives_v25_mechanisms_and_information_gain_question():
    guidance = knowledge.find_symptom_guidance(
        "Tôi đau đầu nhẹ sau khi nhìn màn hình cả ngày."
    )

    assert guidance is not None
    assert guidance["topic"] == "headache"
    assert guidance.get("v25_contextual_reasoning", {}).get("applied") is True
    hypotheses = guidance.get("clinical_hypotheses") or []
    assert any("mỏi thị giác" in value.lower() or "điều tiết" in value.lower() for value in hypotheses)
    questions = guidance.get("clarifying_questions") or []
    assert len(questions) == 1
    assert "đột ngột" in questions[0].lower()


def test_multiturn_headache_guidance_uses_latest_turn_for_delta_but_keeps_screen_trigger():
    guidance = knowledge.find_symptom_guidance(
        "Tôi đau đầu nhẹ sau khi nhìn màn hình cả ngày.\n"
        "Lượt hiện tại: Đau chủ yếu vùng trán, không sốt, nghỉ một lúc thì giảm."
    )

    assert guidance is not None
    trace = guidance.get("v25_contextual_reasoning") or {}
    assert trace.get("user_turns") == 2
    assert trace.get("next_question_key") == "onset_speed"
    assert "fever_neck_stiffness" not in trace.get("unknown_decision_relevant", [])


def test_contextual_overlay_does_not_break_negated_lower_limb_guidance_guard():
    guidance = knowledge.find_symptom_guidance(
        "Tôi chỉ đau ở vùng thắt lưng, không có đau lan hay tê chân."
    )

    assert guidance is not None
    assert guidance["topic"] == "back_pain"
