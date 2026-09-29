"""V27 regression guard for the clinical response-authority facade."""

from pathlib import Path


def test_v27_chat_facade_keeps_needs_information_agent_first() -> None:
    source = Path("app/services/chat.py").read_text(encoding="utf-8")
    # The V26 implementation gated clinical agent-first execution with this
    # conjunction. It must never return.
    assert 'and status == "answered"' not in source
    assert "clinical_request = is_clinical_response_path" in source
    assert "answer_agent_pipeline.generate_response" in source
    assert "clinical_payload_with_outcome" in source
    assert "_core._response = _response" in source
