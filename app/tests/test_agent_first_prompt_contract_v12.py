from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v12_writer_prompt_explicitly_forbids_keyword_to_template_answering():
    text = (ROOT / "app/services/answer_agents.py").read_text(encoding="utf-8")
    assert "Do not map a keyword directly to canned prose" in text
    assert "ORIGINAL COMPOSITION" in text
    assert "do not copy fixed templates" in text


def test_v12_quality_gate_does_not_call_template_repair():
    text = (ROOT / "app/services/output_quality_verifier.py").read_text(encoding="utf-8")
    verify_section = text.split("def verify_output_quality", 1)[1].split("def get_deterministic_template_repair", 1)[0]
    assert "get_deterministic_template_repair(" not in verify_section
    assert "repaired = None" in verify_section
