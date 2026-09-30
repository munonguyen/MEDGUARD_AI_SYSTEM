from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_free_gateway_profile_maps_all_writer_roles_to_gemini_3_8_flash() -> None:
    config = (ROOT / "infrastructure/litellm/config.gemini-free.yaml").read_text(encoding="utf-8")

    assert config.count("model: gemini/gemini-3.8-flash") == 3
    assert "model_name: medguard-answer" in config
    assert "model_name: medguard-clinical-answer" in config
    assert "model_name: medguard-pharma-answer" in config
    assert "gemini-flash-latest" not in config


def test_free_gateway_profile_maps_all_reviewer_roles_to_gemini_3_5_flash_lite() -> None:
    config = (ROOT / "infrastructure/litellm/config.gemini-free.yaml").read_text(encoding="utf-8")

    assert config.count("model: gemini/gemini-3.5-flash-lite") == 3
    assert "model_name: medguard-verifier" in config
    assert "model_name: medguard-clinical-verifier" in config
    assert "model_name: medguard-pharma-verifier" in config
    assert "ollama_chat/" not in config


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


def test_litellm_example_selects_free_profile_by_default() -> None:
    env = (ROOT / "infrastructure/litellm/.env.example").read_text(encoding="utf-8")

    assert "LITELLM_CONFIG_FILE=./config.gemini-free.yaml" in env
    assert "GEMINI_API_KEY=" in env
