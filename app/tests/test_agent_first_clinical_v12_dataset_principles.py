from __future__ import annotations

from app.services.clinical_agent_contract import build_clinical_agent_contract


def test_v12_contract_encodes_behavioral_principles_not_case_templates():
    contract = build_clinical_agent_contract(
        intent="triage",
        question="Tôi đau các khớp tay",
        clinical_result={"urgency": "ROUTINE", "red_flags": []},
    )
    principles = contract.envelope["professional_response_principles"]
    joined = " ".join(principles).lower()

    assert "dangerous action" in joined
    assert "specific action plan" in joined
    assert "single highest-information" in joined
    assert "fixed response templates" in joined

    # The style memory must not carry clinical conclusions from the reference
    # examples into an unrelated case.
    forbidden_case_specific = ("appendicitis", "anaphylaxis", "hepatitis b", "corticoid rebound")
    assert not any(value in joined for value in forbidden_case_specific)
