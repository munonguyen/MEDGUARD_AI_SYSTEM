from __future__ import annotations

import pytest

from app.models.clinical_task import ClinicalTask
from app.services.clinical_agent_contract import build_clinical_agent_contract
from app.services.clinical_task_router import resolve_clinical_task


@pytest.mark.parametrize(
    "prompt",
    [
        "Tôi đau các khớp tay.",
        "Tôi đau khớp tay mấy hôm nay.",
        "toi dau cac khop tay",
        "Mấy khớp ngón tay tôi dạo này đau.",
        "Tôi đau các khớp ngón tay hai bên.",
        "Khớp tay của tôi bị sưng.",
        "Các khớp ngón tay bị sưng và khó cử động.",
        "Buổi sáng tôi bị cứng khớp tay.",
        "Tôi cứng các khớp ngón tay vào buổi sáng.",
        "Tôi đau khớp cổ tay.",
        "Tôi đau khớp bàn tay.",
        "Nhiều khớp tay cùng đau.",
    ],
)
def test_specific_hand_joint_prompts_route_to_peripheral_joint(prompt: str) -> None:
    decision = resolve_clinical_task(prompt)
    assert decision.task == ClinicalTask.PERIPHERAL_JOINT
    assert decision.domain == "peripheral_joint"
    assert decision.confidence >= 0.90


@pytest.mark.parametrize(
    "prompt",
    [
        "Tay tôi khó chịu.",
        "Tôi đau tay.",
        "Tôi mỏi tay sau khi bê đồ.",
        "Tôi đau cánh tay sau khi tập gym.",
        "Tôi tê tay.",
        "Tôi đau cổ lan xuống tay.",
        "Tay tôi lạnh vì phòng điều hòa.",
    ],
)
def test_ambiguous_arm_prompts_are_not_forced_into_peripheral_joint(prompt: str) -> None:
    decision = resolve_clinical_task(prompt)
    assert decision.task != ClinicalTask.PERIPHERAL_JOINT


def test_peripheral_joint_contract_overrides_spine_reasoning() -> None:
    contract = build_clinical_agent_contract(
        intent="triage",
        question="Tôi đau các khớp tay mấy hôm nay.",
        clinical_result={
            "urgency": "ROUTINE",
            "red_flags": [],
            "trace": {
                "details": {
                    "semantic_status": "PARTIALLY_UNDERSTOOD",
                    "confidence": 0.62,
                    "resolution_source": "hybrid",
                }
            },
        },
    )

    episode = contract.envelope["clinical_episode"]
    frame = contract.envelope["reasoning_frame"]
    assert episode is not None
    assert frame is not None
    assert episode["chief_domain"] == "peripheral_joint"
    assert frame["version"] == "v27-peripheral-joint"
    assert frame["next_question_key"] == "joint_inflammation_pattern"
    assert "sưng" in frame["next_best_question"].lower()
    assert "buổi sáng" in frame["next_best_question"].lower()

    rendered_contract = str(frame).lower()
    assert "cauda" not in rendered_contract
    assert "yên ngựa" not in rendered_contract
    assert "tiểu tiện" not in rendered_contract
    assert "yếu chân" not in rendered_contract


def test_peripheral_joint_known_inflammatory_features_move_to_next_unknown() -> None:
    contract = build_clinical_agent_contract(
        intent="triage",
        question="Hai bàn tay đau, các khớp ngón tay sưng nóng và cứng rõ vào buổi sáng.",
        clinical_result={"urgency": "URGENT", "red_flags": []},
    )

    frame = contract.envelope["reasoning_frame"]
    assert frame is not None
    assert frame["next_question_key"] != "joint_inflammation_pattern"
    assert "cauda" not in str(frame).lower()


def test_unresolved_semantics_are_not_reframed_as_routine_fact() -> None:
    contract = build_clinical_agent_contract(
        intent="triage",
        question="Tay tôi cứ kiểu ấy ấy mấy hôm nay.",
        clinical_result={
            "urgency": "ROUTINE",
            "red_flags": [],
            "advice": "Theo dõi tại nhà.",
            "trace": {
                "details": {
                    "semantic_status": "UNRESOLVED",
                    "confidence": 0.20,
                    "resolution_source": "fail_safe",
                }
            },
        },
    )

    assert contract.envelope["assessment_state"] == "INSUFFICIENT_CONTEXT"
    summaries = [c["text"] for c in contract.claims if c["category"] == "summary"]
    actions = [c["text"] for c in contract.claims if c["category"] == "action"]
    assert any("chưa có đủ dữ kiện" in value.lower() for value in summaries)
    assert not any("routine" in value.lower() and "xác định" in value.lower() for value in summaries)
    assert "Theo dõi tại nhà." not in actions


def test_partial_understanding_is_explicitly_distinct_from_urgency() -> None:
    contract = build_clinical_agent_contract(
        intent="triage",
        question="Tôi đau tay nhưng khó tả.",
        clinical_result={
            "urgency": "ROUTINE",
            "red_flags": [],
            "trace": {
                "details": {
                    "semantic_status": "PARTIALLY_UNDERSTOOD",
                    "confidence": 0.58,
                    "resolution_source": "hybrid",
                }
            },
        },
    )
    assert contract.envelope["assessment_state"] == "PARTIALLY_UNDERSTOOD"
    assert contract.envelope["communication_contract"]["separate_epistemic_state_from_urgency"] is True
    assert contract.envelope["communication_contract"]["never_present_unresolved_as_routine_fact"] is True


def test_emergency_authority_wins_even_when_semantics_are_incomplete() -> None:
    contract = build_clinical_agent_contract(
        intent="triage",
        question="Tôi khó tả nhưng đột ngột đau ngực và khó thở dữ dội.",
        clinical_result={
            "urgency": "EMERGENCY",
            "emergency_flag": True,
            "red_flags": ["acute_cardiorespiratory_red_flag"],
            "trace": {
                "details": {
                    "semantic_status": "UNRESOLVED",
                    "confidence": 0.30,
                    "resolution_source": "epistemic_escalation",
                }
            },
        },
    )

    assert contract.envelope["assessment_state"] == "SAFETY_ESCALATED"
    locked_actions = [
        item for item in contract.claims
        if item["category"] == "action" and item["locked"]
    ]
    assert len(locked_actions) == 1
    assert "115" in locked_actions[0]["text"]
    assert not [item for item in contract.claims if item["category"] == "question"]


@pytest.mark.parametrize(
    "prompt",
    [
        "Tôi KHÔNG đau ngực, chỉ đau các khớp tay.",
        "Tôi không khó thở, chỉ đau các khớp ngón tay.",
        "Tôi không sốt nhưng các khớp tay đau.",
        "Tôi không bị ngã, chỉ đau nhiều khớp tay.",
    ],
)
def test_joint_routing_survives_negative_unrelated_red_flags(prompt: str) -> None:
    decision = resolve_clinical_task(prompt)
    assert decision.task == ClinicalTask.PERIPHERAL_JOINT


@pytest.mark.parametrize(
    "prompt",
    [
        "Tôi đau lưng lan xuống chân và tê chân.",
        "Tôi đau cổ lan xuống tay và tê ba ngón.",
        "Sau khi ngã tôi đau cổ tay dữ dội và cổ tay biến dạng.",
        "Tôi bị đau ngực lan ra tay trái khi leo cầu thang.",
    ],
)
def test_near_neighbor_prompts_do_not_use_generic_hand_joint_task(prompt: str) -> None:
    decision = resolve_clinical_task(prompt)
    assert not (
        decision.task == ClinicalTask.PERIPHERAL_JOINT
        and "khop" not in prompt.lower()
    )
