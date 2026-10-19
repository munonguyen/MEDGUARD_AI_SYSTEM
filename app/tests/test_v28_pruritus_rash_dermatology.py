import pytest
from app.models.chat import ChatMessage, ChatRequest
from app.core.context import RequestContext
from app.services.risk_memory import infer_episode_domain
from app.services.rules import triage_rules, is_mild_pruritus_rash_dermatology
from app.services.clinical_episode_model import build_clinical_episode_model
from app.services.contextual_clinical_reasoner import build_contextual_reasoning_frame


def test_dermatology_domain_inference():
    text_turn1 = "tÔI ĐANG BỊ MẨN NGỨA BAN ĐỎ, CẦN CÓ CÁCH KHẮC PHỤC VÀ THUỐC NÀO CÓ THỂ CHỮA ĐƯỢC"
    domain1 = infer_episode_domain(text_turn1)
    assert domain1 == "dermatology"

    text_turn2 = "càng gãi càng ngứa càng rát"
    domain2 = infer_episode_domain(text_turn2)
    assert domain2 == "dermatology"


def test_mild_pruritus_rash_triage_routing():
    text = "tÔI ĐANG BỊ MẨN NGỨA BAN ĐỎ, CẦN CÓ CÁCH KHẮC PHỤC VÀ THUỐC NÀO CÓ THỂ CHỮA ĐƯỢC"
    assert is_mild_pruritus_rash_dermatology(text) is True

    rule_result = triage_rules(text)
    assert rule_result.urgency == "ROUTINE"
    assert rule_result.emergency_flag is False
    assert rule_result.recommended_specialty[0] == "DERMATOLOGY"
    # Ensure clarifying questions are dermatology-specific, not generic fever/pain
    assert any("Ban đỏ" in q or "dùng thuốc mới" in q for q in rule_result.clarifying_questions)
    assert not any("sốt hoặc đau" in q for q in rule_result.clarifying_questions)


def test_turn_progression_question_deduplication():
    # Turn 1
    q1 = "tÔI ĐANG BỊ MẨN NGỨA BAN ĐỎ, CẦN CÓ CÁCH KHẮC PHỤC VÀ THUỐC NÀO CÓ THỂ CHỮA ĐƯỢC"
    ep1 = build_clinical_episode_model(
        episode_id="test-ep-1",
        messages=[{"role": "user", "content": q1}],
    )
    assert ep1.chief_domain == "dermatology"
    reasoning1 = build_contextual_reasoning_frame(ep1, urgency="ROUTINE")
    # In turn 1, airway is critical unknown
    assert reasoning1.next_question_key == "airway_mucosal_involvement"

    # Turn 2: assistant already asked about airway mucosal involvement in Turn 1
    assistant_reply_turn1 = (
        "Bạn nên chườm mát và có thể dùng thuốc kháng histamin H1 thế hệ 2. "
        "Bạn có bị sưng môi, sưng mí mắt, nghẹn họng hoặc cảm giác khó thở không?"
    )
    q2 = "càng gãi càng ngứa càng rát"
    ep2 = build_clinical_episode_model(
        episode_id="test-ep-1",
        messages=[
            {"role": "user", "content": q1},
            {"role": "assistant", "content": assistant_reply_turn1},
            {"role": "user", "content": q2},
        ],
    )
    assert ep2.chief_domain == "dermatology"
    # airway_mucosal_involvement should be filtered out because it was already asked
    unknown_keys = [u.key for u in ep2.unknown_decision_relevant]
    assert "airway_mucosal_involvement" not in unknown_keys

    reasoning2 = build_contextual_reasoning_frame(ep2, urgency="ROUTINE")
    # For scratching/gãi complaint, scratch_skin_damage should be the leading next question
    assert reasoning2.next_question_key == "scratch_skin_damage"
    assert "trầy xước" in (reasoning2.next_best_question or "")
