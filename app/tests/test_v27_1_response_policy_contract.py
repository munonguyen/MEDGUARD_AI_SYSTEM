from __future__ import annotations

from app.services.clinical_agent_contract import ClinicalAgentContract
from app.services.response_policy.contract import apply_response_policy


def _base_contract() -> ClinicalAgentContract:
    return ClinicalAgentContract(
        envelope={
            "intent": "triage",
            "user_question": "Tôi hơi tức cơ ngực sau buổi tập gym tối qua, ấn vào thì đau hơn.",
            "clinical_result": {"urgency": "ROUTINE", "red_flags": []},
            "assessment_state": "UNDERSTOOD",
            "clinical_episode": {
                "unknown_decision_relevant": [
                    {
                        "key": "exertional_pressure",
                        "question": "Bạn có nặng hoặc ép ngực khi đi nhanh hoặc leo cầu thang không?",
                    }
                ]
            },
            "reasoning_frame": {
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
                "next_best_question": "Bạn có nặng hoặc ép ngực khi đi nhanh hoặc leo cầu thang không?",
                "reasoning_limits": [
                    "Đặc điểm cơ học không tự loại trừ nguyên nhân tim-phổi nếu xuất hiện dấu hiệu cảnh báo."
                ],
            },
            "communication_contract": {
                "compose_original_response": True,
                "question_budget": 1,
            },
        },
        claims=[
            {
                "id": "summary_1",
                "category": "summary",
                "text": "Mức xử trí tối thiểu đã được hệ thống an toàn xác định: ROUTINE.",
                "required": True,
                "locked": False,
            },
            {
                "id": "mechanism_2",
                "category": "mechanism",
                "text": "Đặc điểm cơ học có thể phù hợp với đau thành ngực.",
                "required": False,
                "locked": False,
            },
        ],
    )


def test_adapter_removes_technical_triage_summary_from_patient_claims() -> None:
    adapted = apply_response_policy(_base_contract())

    texts = [str(item.get("text")) for item in adapted.claims]
    assert not any("Mức xử trí tối thiểu" in text for text in texts)
    assert adapted.envelope["safety_constraints"]["urgency_floor"] == "ROUTINE"


def test_adapter_promotes_supported_mechanism_to_required_for_d3() -> None:
    adapted = apply_response_policy(_base_contract())

    mechanism = next(item for item in adapted.claims if item["category"] == "mechanism")
    assert mechanism["required"] is True
    contract = adapted.envelope["communication_contract"]
    assert contract["response_depth"] == "D3_CLINICAL_GUIDANCE"
    assert contract["mechanism_required"] is True
    assert contract["reassurance"]["allowed"] is True


def test_adapter_exposes_explanation_frame_for_writer() -> None:
    adapted = apply_response_policy(_base_contract())
    frame = adapted.envelope["explanation_frame"]

    assert "Đặc điểm cơ học" in frame["what_it_may_mean"]
    assert "kích thích" in frame["mechanism"]
    assert "sau buổi tập gym" in frame["why"]
    assert frame["next_best_question"].startswith("Bạn có nặng hoặc ép ngực")
    assert frame["what_would_change_the_assessment"]


def test_emergency_adapter_keeps_action_first_policy() -> None:
    contract = ClinicalAgentContract(
        envelope={
            "intent": "triage",
            "user_question": "Đau ngực lan tay trái, vã mồ hôi và buồn nôn.",
            "clinical_result": {"urgency": "EMERGENCY", "emergency_flag": True},
            "assessment_state": "SAFETY_ESCALATED",
            "clinical_episode": {},
            "reasoning_frame": {"mechanisms": []},
            "communication_contract": {},
        },
        claims=[
            {
                "id": "action_1",
                "category": "action",
                "text": "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức.",
                "required": True,
                "locked": True,
            }
        ],
    )

    adapted = apply_response_policy(contract)
    policy = adapted.envelope["response_policy"]

    assert policy["response_depth"] == "D5_EMERGENCY"
    assert policy["action_first"] is True
    assert policy["question_budget"] == 0
    assert adapted.envelope["safety_constraints"]["cannot_be_lowered_by_writer"] is True
