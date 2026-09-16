from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models.triage import VitalSigns
from app.services.agent_provider import LiteLLMResponsesProvider
from app.services.answer_agents import answer_agent_pipeline
from app.services.rules import triage_rules
from scripts.bootstrap_litellm_key import DEFAULT_MODELS


client = TestClient(app)
ROOT_DIR = Path(__file__).resolve().parents[2]


def _headers(key: str) -> dict[str, str]:
    return {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "Idempotency-Key": key,
    }


def _point(metric: str, value: float, unit: str, hour: int) -> dict:
    return {
        "metric": metric,
        "value": value,
        "unit": unit,
        "recorded_at": f"2026-09-07T{hour:02d}:00:00Z",
    }


def test_readiness_reports_real_development_backends():
    response = client.get("/v1/health/readiness")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["production_ready"] is False
    checks = {check["name"]: check for check in body["checks"]}
    assert checks["database"]["detail"] == "active backend: sqlite-memory"
    assert checks["queue"]["detail"].startswith("active backend: memory;")
    assert "dead_letter=" in checks["queue"]["detail"]
    assert checks["ocr_engines"]["status"] == "fail"
    assert "gateway_response_coverage" in checks


def test_runtime_answer_agents_only_use_the_llm_gateway():
    assert isinstance(
        answer_agent_pipeline.research_provider, LiteLLMResponsesProvider
    )
    assert isinstance(
        answer_agent_pipeline.verifier_provider, LiteLLMResponsesProvider
    )
    assert answer_agent_pipeline.research_provider.provider_name == "llm-gateway"
    assert answer_agent_pipeline.verifier_provider.provider_name == "llm-gateway"


def test_gateway_has_fixed_agent_role_bindings():
    config = (ROOT_DIR / "infrastructure/litellm/config.yaml").read_text(encoding="utf-8")
    production_env = (ROOT_DIR / ".env.production.example").read_text(encoding="utf-8")

    assert config.count("model_name:") == 6
    assert "model_name: medguard-answer" in config
    assert "model_name: medguard-verifier" in config
    assert "model_name: medguard-clinical-answer" in config
    assert "model_name: medguard-clinical-verifier" in config
    assert "model_name: medguard-pharma-answer" in config
    assert "model_name: medguard-pharma-verifier" in config
    assert "cross-provider" not in config
    assert "\n  fallbacks:" not in config
    assert DEFAULT_MODELS == (
        "medguard-answer",
        "medguard-verifier",
        "medguard-clinical-answer",
        "medguard-clinical-verifier",
        "medguard-pharma-answer",
        "medguard-pharma-verifier",
    )
    assert "MEDGUARD_AGENT_MODE=enforced" in production_env
    assert "MEDGUARD_AGENT_COVERAGE_SCOPE=all" in production_env


def test_cloud_gateway_uses_gemini_analysis_and_openai_judgment():
    config = (ROOT_DIR / "infrastructure/litellm/config.yaml").read_text(encoding="utf-8")

    assert config.count("model: gemini/gemini-3.8-flash") == 3
    assert config.count("reasoning_effort: low") == 3
    assert config.count("model: openai/gpt-5.6-sol") == 3
    assert "gemini/gemini-3.1-pro-preview" not in config
    assert "api_key: os.environ/GEMINI_API_KEY" in config
    assert "api_key: os.environ/OPENAI_API_KEY" in config


def test_free_mixed_gateway_never_claims_a_chatgpt_judge():
    config = (ROOT_DIR / "infrastructure/litellm/config.gemini-free.yaml").read_text(
        encoding="utf-8"
    )

    assert config.count("model_name:") == 6
    assert config.count("model: gemini/gemini-2.5-flash") == 3
    assert config.count("model: ollama_chat/medgemma1.5:4b") == 3
    assert "openai/" not in config
    assert "supported_environments: [development, staging]" in config


def test_gateway_env_example_contains_no_provider_credentials():
    env_example = (ROOT_DIR / "infrastructure/litellm/.env.example").read_text(
        encoding="utf-8"
    )

    assert "GEMINI_API_KEY=\n" in env_example
    assert "OPENAI_API_KEY=\n" in env_example
    assert "AQ." not in env_example


def test_single_critical_monitoring_point_is_never_suppressed():
    response = client.post(
        "/v1/monitoring/ingest",
        headers=_headers("monitor-single-critical"),
        json={
            "patient_ref": "p-critical",
            "metrics": [_point("spo2", 89, "%", 8)],
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert body["trend"] == "worsening"
    assert body["escalation_level"] == "EMERGENCY"
    assert body["metrics"][0]["direction"] == "unknown"


def test_monitoring_requires_three_points_for_the_same_metric():
    response = client.post(
        "/v1/monitoring/ingest",
        headers=_headers("monitor-per-metric-count"),
        json={
            "patient_ref": "p-count",
            "metrics": [
                _point("spo2", 98, "%", 8),
                _point("heart_rate", 80, "bpm", 9),
                _point("temperature_c", 37, "C", 10),
            ],
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "unknown"
    assert body["trend"] == "insufficient_data"
    assert all(metric["direction"] == "unknown" for metric in body["metrics"])


def test_spo2_trend_uses_lower_is_worse_semantics():
    worsening = client.post(
        "/v1/monitoring/ingest",
        headers=_headers("monitor-spo2-down"),
        json={
            "patient_ref": "p-spo2",
            "metrics": [
                _point("spo2", 98, "%", 8),
                _point("spo2", 96, "%", 9),
                _point("spo2", 94, "%", 10),
            ],
        },
    )
    improving = client.post(
        "/v1/monitoring/ingest",
        headers=_headers("monitor-spo2-up"),
        json={
            "patient_ref": "p-spo2",
            "metrics": [
                _point("spo2", 94, "%", 8),
                _point("spo2", 96, "%", 9),
                _point("spo2", 98, "%", 10),
            ],
        },
    )
    assert worsening.json()["trend"] == "worsening"
    assert worsening.json()["escalation_level"] == "CLINIC"
    assert improving.json()["trend"] == "improving"
    assert improving.json()["escalation_level"] == "NONE"


def test_monitoring_rejects_wrong_unit_and_impossible_value():
    wrong_unit = client.post(
        "/v1/monitoring/ingest",
        headers=_headers("monitor-wrong-unit"),
        json={"patient_ref": "p-invalid", "metrics": [_point("spo2", 98, "mg", 8)]},
    )
    impossible = client.post(
        "/v1/monitoring/ingest",
        headers=_headers("monitor-impossible"),
        json={"patient_ref": "p-invalid", "metrics": [_point("pain_score", 11, "/10", 8)]},
    )
    assert wrong_unit.status_code == 400
    assert impossible.status_code == 400


def test_warning_vital_is_urgent_not_emergency():
    result = triage_rules(
        "kiem tra sinh hieu",
        vitals=VitalSigns(spo2=93, heart_rate=80, systolic=120, diastolic=80),
    )
    assert result.urgency == "URGENT"
    assert result.emergency_flag is False
    assert result.esi_level == 3


def test_critical_vital_remains_emergency():
    result = triage_rules(
        "kiem tra sinh hieu",
        vitals=VitalSigns(spo2=89, heart_rate=80, systolic=120, diastolic=80),
    )
    assert result.urgency == "EMERGENCY"
    assert result.emergency_flag is True
    assert result.esi_level == 1
