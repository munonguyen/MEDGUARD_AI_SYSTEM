from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v27_free_gateway_profile_uses_flash_lite_for_all_mandatory_roles() -> None:
    config = (ROOT / "infrastructure/litellm/config.gemini-v27-free.yaml").read_text(
        encoding="utf-8"
    )

    assert config.count("model_name:") == 6
    assert config.count("model: gemini/gemini-3.5-flash-lite") == 6
    assert "model: gemini/gemini-3.5-flash\n" not in config
    assert "model: gemini/gemini-3.8-flash" not in config
    assert "model_name: medguard-answer" in config
    assert "model_name: medguard-clinical-answer" in config
    assert "model_name: medguard-pharma-answer" in config
    assert "model_name: medguard-verifier" in config
    assert "model_name: medguard-clinical-verifier" in config
    assert "model_name: medguard-pharma-verifier" in config
    assert "\n  fallbacks:" not in config


def test_v27_quality_profile_keeps_3_8_writer_and_3_5_reviewer_separation() -> None:
    config = (ROOT / "infrastructure/litellm/config.gemini-v27-quality.yaml").read_text(
        encoding="utf-8"
    )

    assert config.count("model: gemini/gemini-3.8-flash") == 3
    assert config.count("model: gemini/gemini-3.5-flash-lite") == 3
    assert "\n  fallbacks:" not in config


def test_application_free_profile_is_sync_enforced_not_shadow() -> None:
    env = (ROOT / ".env.gemini-free.example").read_text(encoding="utf-8")

    assert "MEDGUARD_AGENT_MODE=enforced" in env
    assert "MEDGUARD_AGENT_COVERAGE_SCOPE=all" in env
    assert "MEDGUARD_AGENT_SYNC_ENABLED=true" in env
    assert "MEDGUARD_AGENT_BACKGROUND_ENABLED=false" in env


def test_free_profile_does_not_require_hosted_search_to_release_an_answer() -> None:
    env = (ROOT / ".env.gemini-free.example").read_text(encoding="utf-8")

    assert "MEDGUARD_AGENT_WEB_SEARCH_REQUIRED=false" in env
    assert "MEDGUARD_VERIFIER_WEB_SEARCH_REQUIRED=false" in env


def test_runtime_configurator_selects_v27_free_profile() -> None:
    setup = (ROOT / "scripts/configure_gemini_free.sh").read_text(encoding="utf-8")

    assert "LITELLM_CONFIG_FILE=./config.gemini-v27-free.yaml" in setup
    assert "DEFAULT_KEY_B64" not in setup
    assert "--default" not in setup
