from app.services import answering
from app.services.clinical_agent_contract import build_clinical_agent_contract
from app.services.clinical_contract_fallback import compose_contract_fallback


def test_contract_fallback_names_medicines_without_machine_risk_code() -> None:
    result = {
        "overall_risk": "HIGH",
        "urgency": "URGENT",
        "requires_human_review": True,
        "warnings": [
            {
                "type": "DRUG_DRUG_INTERACTION",
                "tier": "HARD_STOP",
                "medication": "ibuprofen",
                "detail": "Phối hợp có thể làm tăng nguy cơ chảy máu.",
            }
        ],
        "conversation_current_medications": ["warfarin"],
        "conversation_proposed_medications": ["ibuprofen"],
    }
    base = answering.build_grounded_answer(
        intent="safety",
        status="answered",
        reply="unused",
        required_fields=[],
        result=result,
    )
    contract = build_clinical_agent_contract(
        intent="safety",
        question="Tôi đang dùng warfarin, có dùng ibuprofen được không?",
        clinical_result=result,
    )
    final = compose_contract_fallback(base, contract)
    visible = " ".join([final.title, final.summary, *final.key_points, *final.next_steps])
    assert "warfarin" in visible.lower()
    assert "ibuprofen" in visible.lower()
    assert "HIGH" not in visible
    assert "MODERATE" not in visible
    assert "LOW" not in visible


def test_contract_fallback_preserves_hard_stop_action() -> None:
    result = {
        "overall_risk": "HIGH",
        "urgency": "URGENT",
        "requires_human_review": True,
        "warnings": [
            {
                "type": "DRUG_DRUG_INTERACTION",
                "tier": "HARD_STOP",
                "medication": "ibuprofen",
                "detail": "Phối hợp có thể làm tăng nguy cơ chảy máu.",
            }
        ],
        "conversation_current_medications": ["warfarin"],
        "conversation_proposed_medications": ["ibuprofen"],
    }
    base = answering.build_grounded_answer(
        intent="safety",
        status="answered",
        reply="unused",
        required_fields=[],
        result=result,
    )
    contract = build_clinical_agent_contract(
        intent="safety",
        question="Tôi đang dùng warfarin, có dùng ibuprofen được không?",
        clinical_result=result,
    )
    final = compose_contract_fallback(base, contract)
    action_text = " ".join(final.next_steps).lower()
    assert "không tự" in action_text
    assert "bác sĩ" in action_text or "dược sĩ" in action_text
