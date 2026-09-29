"""V27 regression guard for the clinical response-authority facade.

This file exists so the repository cannot silently collapse ``chat.py`` back
into the monolithic V26 implementation and reintroduce ``status == answered``
as the switch between agent-first and legacy clinical contracts.
"""

from pathlib import Path


def test_v27_chat_facade_keeps_needs_information_agent_first() -> None:
    source = Path("app/services/chat.py").read_text(encoding="utf-8")
    assert "status == \"answered\"" not in source
    assert "clinical_request" in source
    assert "answer_agent_pipeline.generate_response" in source
    assert "clinical_payload[\"_response_status\"] = status" in source
    assert "_core._response = _response" in source
