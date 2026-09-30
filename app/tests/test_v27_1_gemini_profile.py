from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def test_v27_free_profile_uses_quota_stable_gemini_aliases() -> None:
    config = (ROOT_DIR / "infrastructure/litellm/config.gemini-v27-free.yaml").read_text(
        encoding="utf-8"
    )

    # The FREE development profile intentionally keeps all six role aliases on
    # Flash-Lite because the free-tier project exhausted the daily quota for the
    # stronger Flash variants during repeated stability certification. Role
    # separation is contractual even when model-family independence is not
    # available in this quota-limited profile.
    assert config.count("model_name:") == 6
    assert config.count("model: gemini/gemini-3.5-flash-lite") == 6
    assert "model: gemini/gemini-3.8-flash" not in config
    assert "ollama_chat/" not in config
    assert "openai/" not in config


def test_v27_free_profile_never_promotes_reviewer_to_writer_fallback() -> None:
    config = (ROOT_DIR / "infrastructure/litellm/config.gemini-v27-free.yaml").read_text(
        encoding="utf-8"
    )

    assert "fallbacks:" not in config
    assert "medguard-clinical-answer: [\"medguard-clinical-verifier\"]" not in config
    assert "medguard-answer: [\"medguard-verifier\"]" not in config
    assert "medguard-pharma-answer: [\"medguard-pharma-verifier\"]" not in config


def test_local_setup_selects_v27_free_profile() -> None:
    setup = (ROOT_DIR / "scripts/configure_gemini_free.sh").read_text(encoding="utf-8")
    assert "LITELLM_CONFIG_FILE=./config.gemini-v27-free.yaml" in setup
