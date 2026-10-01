from __future__ import annotations

from app.services.response_policy import (
    CommunicationGoal,
    ResponseDepth,
    build_response_policy,
)


def _mechanical_chest_reasoning() -> dict:
    return {
        "mechanisms": [
            {
                "hypothesis_id": "chest_wall_mechanical",
                "role": "leading",
                "support_level": "plausible",
                "mechanism": (
                    "Đau tăng khi ấn hoặc sau vận động cơ có thể phù hợp với kích thích "
                    "cơ-xương thành ngực."
                ),
                "evidence_for": ["sau buổi tập gym", "ấn vào đau hơn"],
                "patient_safe_statement": (
                    "Đặc điểm cơ học làm nguyên nhân thành ngực hợp lý hơn, nhưng không tự "
                    "loại trừ nguyên nhân tim-phổi."
                ),
            }
        ],
        "reasoning_limits": [
            "Đặc điểm cơ học không tự loại trừ nguyên nhân tim-phổi nếu xuất hiện dấu hiệu cảnh báo."
        ],
    }


def test_low_risk_mechanical_chest_pain_gets_d3_calibrated_reassurance() -> None:
    policy = build_response_policy(
        intent="triage",
        question="Tôi hơi tức cơ ngực sau buổi tập gym tối qua, ấn vào thì đau hơn.",
        urgency="ROUTINE",
        assessment_state="UNDERSTOOD",
        result={"urgency": "ROUTINE", "red_flags": []},
        reasoning_payload=_mechanical_chest_reasoning(),
    )

    assert policy.communication_goal == CommunicationGoal.REASSURE_AND_GUIDE
    assert policy.response_depth == ResponseDepth.D3_CLINICAL_GUIDANCE
    assert policy.explanation_required is True
    assert policy.mechanism_required is True
    assert policy.reassurance.allowed is True
    assert policy.reassurance.strength == "cautious"
    assert "sau buổi tập gym" in policy.reassurance.basis
    assert policy.question_budget == 1
    assert policy.target_length.min_words == 120
    assert policy.target_length.max_words == 220


def test_emergency_response_is_action_first_and_has_no_question_budget() -> None:
    policy = build_response_policy(
        intent="triage",
        question="Đau ngực lan tay trái, vã mồ hôi và buồn nôn.",
        urgency="EMERGENCY",
        assessment_state="SAFETY_ESCALATED",
        result={"urgency": "EMERGENCY", "emergency_flag": True},
        reasoning_payload={"mechanisms": []},
    )

    assert policy.communication_goal == CommunicationGoal.EMERGENCY_ACTION
    assert policy.response_depth == ResponseDepth.D5_EMERGENCY
    assert policy.action_first is True
    assert policy.question_budget == 0
    assert policy.reassurance.allowed is False
    assert policy.target_length.max_words <= 140


def test_urgent_exertional_symptom_prioritizes_explanation_and_action() -> None:
    policy = build_response_policy(
        intent="triage",
        question="Hôm nay đi bộ nhanh thì cảm giác nặng ngực rõ hơn và hơi hụt hơi.",
        urgency="URGENT",
        assessment_state="UNDERSTOOD",
        result={"urgency": "URGENT", "red_flags": ["gắng sức", "khó thở"]},
        reasoning_payload={
            "mechanisms": [
                {
                    "role": "must_not_miss_pathway",
                    "support_level": "supported",
                    "mechanism": "Gắng sức làm tăng nhu cầu oxy của cơ thể.",
                }
            ]
        },
    )

    assert policy.communication_goal == CommunicationGoal.URGENT_GUIDANCE
    assert policy.response_depth == ResponseDepth.D4_URGENT
    assert policy.explanation_required is True
    assert policy.reassurance.allowed is False
    assert "why_concerning" in policy.required_sections


def test_insufficient_context_is_not_reassured_as_routine() -> None:
    policy = build_response_policy(
        intent="triage",
        question="Tôi đau các khớp tay.",
        urgency="ROUTINE",
        assessment_state="INSUFFICIENT_CONTEXT",
        result={"urgency": "ROUTINE", "red_flags": []},
        reasoning_payload={"mechanisms": []},
    )

    assert policy.communication_goal == CommunicationGoal.CLARIFY_UNCERTAINTY
    assert policy.reassurance.allowed is False
    assert policy.question_budget == 1
    assert "highest_information_question" in policy.required_sections


def test_simple_health_information_question_gets_short_direct_depth() -> None:
    policy = build_response_policy(
        intent="triage",
        question="Sốt là bao nhiêu độ?",
        urgency="ROUTINE",
        assessment_state="UNDERSTOOD",
        result={"urgency": "ROUTINE", "red_flags": []},
        reasoning_payload=None,
    )

    assert policy.communication_goal == CommunicationGoal.EDUCATE
    assert policy.response_depth == ResponseDepth.D1_DIRECT
    assert policy.question_budget == 0
    assert policy.target_length.max_words <= 90


def test_disease_education_question_does_not_force_patient_triage() -> None:
    policy = build_response_policy(
        intent="triage",
        question="Viêm khớp dạng thấp là gì?",
        urgency="ROUTINE",
        assessment_state="UNDERSTOOD",
        result={"urgency": "ROUTINE", "red_flags": []},
        reasoning_payload=None,
    )

    assert policy.communication_goal == CommunicationGoal.EDUCATE
    assert policy.response_depth == ResponseDepth.D2_EXPLAIN
    assert policy.question_budget == 0
    assert policy.reassurance.allowed is False
