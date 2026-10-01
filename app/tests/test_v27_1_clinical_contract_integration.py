from __future__ import annotations

from app.services.clinical_agent_contract import build_clinical_agent_contract


def test_post_gym_reproducible_chest_pain_requires_explanation_and_calibrated_reassurance() -> None:
    contract = build_clinical_agent_contract(
        intent="triage",
        question="Tôi hơi tức cơ ngực sau buổi tập gym tối qua, ấn vào thì đau hơn.",
        clinical_result={
            "urgency": "ROUTINE",
            "red_flags": [],
            "advice": "Tạm tránh bài tập ngực nặng và theo dõi diễn biến.",
        },
    )

    policy = contract.envelope["response_policy"]
    communication = contract.envelope["communication_contract"]
    frame = contract.envelope["explanation_frame"]

    assert policy["response_depth"] == "D3_CLINICAL_GUIDANCE"
    assert policy["communication_goal"] == "reassure_and_guide"
    assert policy["reassurance"]["allowed"] is True
    assert communication["mechanism_required"] is True
    assert communication["reassurance_must_be_evidence_bounded"] is True
    assert frame["mechanism"]
    assert frame["what_it_may_mean"]

    mechanism_claims = [claim for claim in contract.claims if claim["category"] == "mechanism"]
    assert mechanism_claims
    assert all(claim["required"] is True for claim in mechanism_claims)

    patient_claim_text = "\n".join(str(claim["text"]) for claim in contract.claims)
    assert "Mức xử trí tối thiểu đã được hệ thống an toàn xác định" not in patient_claim_text


def test_exertional_chest_pressure_gets_urgent_explanation_policy() -> None:
    contract = build_clinical_agent_contract(
        intent="triage",
        question="Hôm nay đi bộ nhanh thì cảm giác nặng ngực rõ hơn và hơi hụt hơi.",
        clinical_result={
            "urgency": "URGENT",
            "red_flags": ["nặng ngực khi gắng sức", "hụt hơi"],
        },
    )

    policy = contract.envelope["response_policy"]
    assert policy["response_depth"] == "D4_URGENT"
    assert policy["reassurance"]["allowed"] is False
    assert "why_concerning" in policy["required_sections"]
    assert contract.envelope["safety_constraints"]["urgency_floor"] == "URGENT"


def test_emergency_contract_is_action_first_and_zero_question() -> None:
    contract = build_clinical_agent_contract(
        intent="triage",
        question="Bây giờ đau lan xuống tay trái, vã mồ hôi và buồn nôn.",
        clinical_result={
            "urgency": "EMERGENCY",
            "emergency_flag": True,
            "red_flags": ["đau lan tay trái", "vã mồ hôi", "buồn nôn"],
        },
    )

    policy = contract.envelope["response_policy"]
    assert policy["response_depth"] == "D5_EMERGENCY"
    assert policy["action_first"] is True
    assert policy["question_budget"] == 0
    assert contract.envelope["communication_contract"]["emergency_action_precedes_explanation"] is True

    action_claims = [claim for claim in contract.claims if claim["category"] == "action"]
    assert action_claims
    assert any("115" in str(claim["text"]) for claim in action_claims)


def test_uncertain_joint_complaint_does_not_receive_false_reassurance() -> None:
    contract = build_clinical_agent_contract(
        intent="triage",
        question="Tôi đau các khớp tay.",
        clinical_result={
            "urgency": "ROUTINE",
            "red_flags": [],
            "trace": {
                "details": {
                    "semantic_status": "UNRESOLVED",
                    "confidence": 0.0,
                    "resolution_source": "needs_information_contract",
                }
            },
        },
    )

    policy = contract.envelope["response_policy"]
    assert policy["communication_goal"] == "clarify_uncertainty"
    assert policy["reassurance"]["allowed"] is False
    assert policy["question_budget"] == 1

    question_claims = [claim for claim in contract.claims if claim["category"] == "question"]
    assert len(question_claims) == 1
    assert question_claims[0]["required"] is True
