from __future__ import annotations

import inspect
from types import SimpleNamespace

from app.services import chat
from app.services.agent_graph import _agent_inputs


def test_single_path_scope_cannot_be_bypassed_by_chat_branches():
    response_source = inspect.getsource(chat._response)
    orchestration_source = inspect.getsource(chat.orchestrate_chat)

    assert "effective_allow_agent" in response_source
    assert 'settings.agent_coverage_scope == "all"' in response_source
    assert "allow_agent=False" not in orchestration_source


def test_legacy_presentation_prose_is_hidden_from_writer_and_reviewer():
    state = SimpleNamespace(
        intent="general",
        question="Tôi cần làm gì tiếp theo?",
        patient_context={"age": 30, "patient_ref": "PHI-MUST-NOT-PASS"},
        claims=[
            {"id": "title_1", "category": "title", "text": "Legacy title", "locked": False},
            {"id": "summary_2", "category": "summary", "text": "Legacy summary", "locked": False},
            {"id": "safety_3", "category": "safety", "text": "Safety constraint", "locked": True},
        ],
        tool_result={
            "title": "Legacy title",
            "summary": "Legacy summary",
            "narrative": [{"text": "Legacy patient-facing prose"}],
            "key_points": ["Structured finding"],
            "next_steps": ["Structured action"],
            "safety_notes": ["Safety constraint"],
            "questions": ["One clarification?"],
            "decision_basis": "versioned_rules",
            "evidence_state": "bounded_result",
            "requires_human_review": False,
        },
    )

    claims, envelope = _agent_inputs(state)  # type: ignore[arg-type]

    assert {claim["category"] for claim in claims} == {"safety"}
    assert "title" not in envelope
    assert "summary" not in envelope
    assert "narrative" not in envelope
    assert envelope["key_points"] == ["Structured finding"]
    assert envelope["next_steps"] == ["Structured action"]
    assert envelope["patient_context"] == {"age": 30}
    assert envelope["communication_contract"]["compose_original_response"] is True
    assert envelope["communication_contract"]["reviewer_is_non_authoring"] is True


def test_native_agent_first_envelope_is_not_reduced():
    native = {
        "version": "v12-agent-first",
        "intent": "triage",
        "clinical_result": {"urgency": "URGENT"},
    }
    expected_claims = [
        {"id": "summary_1", "category": "summary", "text": "URGENT", "locked": False}
    ]
    state = SimpleNamespace(
        intent="triage",
        question="Đau nhiều",
        patient_context={},
        claims=expected_claims,
        tool_result=native,
    )

    claims, envelope = _agent_inputs(state)  # type: ignore[arg-type]

    assert claims == expected_claims
    assert envelope is native
