from __future__ import annotations

import pytest

from app.services.clinical_agent_contract import build_clinical_agent_contract
from app.services.clinical_task_router import resolve_clinical_task
from app.models.clinical_task import ClinicalTask


@pytest.mark.parametrize(
    ("prompt", "forbidden_terms"),
    [
        ("Các khớp ngón tay tôi dạo này đau.", ("cauda", "yên ngựa", "tiểu tiện", "yếu chân")),
        ("Khớp ngón tay tôi sưng và đau.", ("cauda", "rối loạn đại tiện", "foot drop")),
        ("Tôi đau các khớp bàn tay.", ("đau lưng", "cột sống thắt lưng", "yếu chân")),
        ("Tôi cứng các khớp tay vào buổi sáng.", ("mất kiểm soát tiểu", "tê vùng yên ngựa")),
    ],
)
def test_joint_contract_never_leaks_spine_specific_content(prompt: str, forbidden_terms: tuple[str, ...]) -> None:
    contract = build_clinical_agent_contract(
        intent="triage",
        question=prompt,
        clinical_result={
            "urgency": "ROUTINE",
            "red_flags": [],
            "trace": {"details": {"semantic_status": "PARTIALLY_UNDERSTOOD", "confidence": 0.62}},
        },
    )
    surface = " ".join(
        [
            str(contract.envelope.get("clinical_episode") or {}),
            str(contract.envelope.get("reasoning_frame") or {}),
            " ".join(item["text"] for item in contract.claims),
        ]
    ).lower()
    assert contract.envelope["clinical_episode"]["chief_domain"] == "peripheral_joint"
    for term in forbidden_terms:
        assert term not in surface


@pytest.mark.parametrize(
    "prompt",
    [
        "Các khớp ngón tay tôi dạo này đau.",
        "Khớp ngón tay bên phải đau mấy ngày nay.",
        "Các khớp tay của tôi bị sưng.",
        "Hai bên khớp ngón tay đều đau.",
        "Buổi sáng các khớp tay cứng và khó cử động.",
        "toi bi dau o cac khop ngon tay",
        "khop ngon tay cua toi bi sung va dau",
        "may khop tay cua toi hom nay nhuc",
    ],
)
def test_word_order_and_no_accent_variants_preserve_joint_semantics(prompt: str) -> None:
    task = resolve_clinical_task(prompt)
    assert task.task == ClinicalTask.PERIPHERAL_JOINT

    contract = build_clinical_agent_contract(
        intent="triage",
        question=prompt,
        clinical_result={
            "urgency": "ROUTINE",
            "red_flags": [],
            "trace": {"details": {"semantic_status": "UNRESOLVED", "confidence": 0.30}},
        },
    )
    assert contract.envelope["assessment_state"] == "INSUFFICIENT_CONTEXT"
    assert contract.envelope["clinical_episode"]["chief_domain"] == "peripheral_joint"
    assert contract.envelope["reasoning_frame"]["version"] == "v27-peripheral-joint"


@pytest.mark.parametrize(
    "prompt",
    [
        "Tay tôi cứ kiểu ấy ấy mấy hôm nay.",
        "Tôi thấy tay hơi lạ nhưng khó tả.",
        "Chỗ tay này khó chịu lắm mà tôi không biết diễn tả.",
        "tay toi cu ky ky sao ay",
    ],
)
def test_ambiguous_language_does_not_create_confident_clinical_claim(prompt: str) -> None:
    contract = build_clinical_agent_contract(
        intent="triage",
        question=prompt,
        clinical_result={
            "urgency": "ROUTINE",
            "red_flags": [],
            "advice": "Theo dõi tại nhà.",
            "trace": {
                "details": {
                    "semantic_status": "UNRESOLVED",
                    "confidence": 0.15,
                    "resolution_source": "fail_safe",
                }
            },
        },
    )
    assert contract.envelope["assessment_state"] == "INSUFFICIENT_CONTEXT"
    text = " ".join(item["text"] for item in contract.claims).lower()
    assert "theo dõi tại nhà" not in text
    assert "chưa có đủ dữ kiện" in text


@pytest.mark.parametrize(
    ("prompt", "expected_not_joint"),
    [
        ("Tôi đau cổ lan xuống tay và tê ba ngón.", True),
        ("Tôi đau ngực lan ra tay trái khi leo cầu thang.", True),
        ("Tôi ngã chống tay, cổ tay biến dạng và rất đau.", True),
        ("Tôi chỉ mỏi bắp tay sau khi tập gym.", True),
        ("Tay tôi lạnh vì ngồi điều hòa.", True),
        ("Tôi tê cả bàn tay nhưng không đau khớp.", True),
    ],
)
def test_near_neighbor_body_site_language_is_not_misrouted(prompt: str, expected_not_joint: bool) -> None:
    decision = resolve_clinical_task(prompt)
    if expected_not_joint:
        assert decision.task != ClinicalTask.PERIPHERAL_JOINT
