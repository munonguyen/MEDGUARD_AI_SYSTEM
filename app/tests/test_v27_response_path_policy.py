from app.services.response_path_policy import (
    clinical_payload_with_outcome,
    is_clinical_response_path,
)


def test_needs_information_does_not_change_clinicality() -> None:
    assert is_clinical_response_path(intent="triage", clinical_task_name=None)
    assert is_clinical_response_path(intent="safety", clinical_task_name=None)
    assert is_clinical_response_path(intent="general", clinical_task_name="LAB_INTERPRETATION")
    assert is_clinical_response_path(intent="general", clinical_task_name="PERIPHERAL_JOINT")
    assert not is_clinical_response_path(intent="fhir", clinical_task_name=None)


def test_outcome_metadata_is_carried_inside_clinical_contract_payload() -> None:
    payload = clinical_payload_with_outcome(
        {"urgency": "ROUTINE"},
        status="needs_information",
        required_fields=["proposed_medications"],
        extracted={"clinical_task": "PERIPHERAL_JOINT"},
    )
    assert payload["urgency"] == "ROUTINE"
    assert payload["_response_status"] == "needs_information"
    assert payload["required_fields"] == ["proposed_medications"]
    assert payload["extracted"]["clinical_task"] == "PERIPHERAL_JOINT"
