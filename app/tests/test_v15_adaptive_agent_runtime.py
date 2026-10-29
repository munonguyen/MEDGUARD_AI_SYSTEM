from __future__ import annotations

from app.models.adaptive_routing import AdaptiveRouteDecision, ModelTier, SeverityAgent, SeverityChoice
from app.services.adaptive_agent_runtime import AdaptiveAgentRuntime, AdaptiveAgentRuntimeConfig


def _route(tier: ModelTier) -> AdaptiveRouteDecision:
    return AdaptiveRouteDecision(
        clinical_task="acute_symptom",
        resolved_severity="ROUTINE" if tier != ModelTier.DEEP else "EMERGENCY",
        agent=SeverityAgent.ROUTINE if tier != ModelTier.DEEP else SeverityAgent.EMERGENCY,
        model_tier=tier,
        emergency_lock=tier == ModelTier.DEEP,
        kev_choice=SeverityChoice.ROUTINE if tier != ModelTier.DEEP else SeverityChoice.EMERGENCY,
        confidence=0.95,
        margin=0.8,
        fact_coverage=0.95,
    )


def test_writer_model_ladder_keeps_fallback_orthogonal_to_severity() -> None:
    runtime = AdaptiveAgentRuntime(
        AdaptiveAgentRuntimeConfig(
            mode="enforced",
            fast_writer_model="fast-a",
            standard_writer_model="standard-a",
            deep_writer_model="deep-a",
            writer_fallback_models=("backup-b", "backup-c"),
        )
    )

    assert runtime.writer_models(route=_route(ModelTier.FAST), default_model="clinical-default") == (
        "fast-a",
        "clinical-default",
        "backup-b",
        "backup-c",
    )
    assert runtime.writer_models(route=_route(ModelTier.DEEP), default_model="clinical-default") == (
        "deep-a",
        "clinical-default",
        "backup-b",
        "backup-c",
    )


def test_model_ladder_deduplicates_models() -> None:
    runtime = AdaptiveAgentRuntime(
        AdaptiveAgentRuntimeConfig(
            fast_writer_model="same",
            writer_fallback_models=("same", "backup", "backup"),
            verifier_fallback_models=("judge", "judge", "judge-backup"),
        )
    )

    assert runtime.writer_models(route=_route(ModelTier.FAST), default_model="same") == ("same", "backup")
    assert runtime.verifier_models(default_model="judge") == ("judge", "judge-backup")


def test_runtime_reads_clinical_result_without_mutating_it() -> None:
    clinical_result = {
        "urgency": "URGENT",
        "clinical_task": "acute_symptom",
        "trace": {"details": {"fact_coverage": 0.9}},
    }
    envelope = {"clinical_result": clinical_result}
    runtime = AdaptiveAgentRuntime(AdaptiveAgentRuntimeConfig(mode="shadow"))

    route = runtime.resolve(envelope=envelope, patient_context={"age": 25})

    assert route is not None
    assert route.resolved_severity == "URGENT"
    assert route.agent == SeverityAgent.URGENT
    assert clinical_result["urgency"] == "URGENT"


def test_runtime_returns_none_for_non_clinical_envelope() -> None:
    runtime = AdaptiveAgentRuntime(AdaptiveAgentRuntimeConfig(mode="shadow"))
    assert runtime.resolve(envelope={"intent": "general"}, patient_context={}) is None


def test_verifier_ladder_always_keeps_primary_first() -> None:
    runtime = AdaptiveAgentRuntime(
        AdaptiveAgentRuntimeConfig(verifier_fallback_models=("judge-b", "judge-c"))
    )
    assert runtime.verifier_models(default_model="judge-a") == ("judge-a", "judge-b", "judge-c")


def test_fast_route_reduces_writer_token_budget() -> None:
    runtime = AdaptiveAgentRuntime(
        AdaptiveAgentRuntimeConfig(
            fast_max_input_tokens=6000,
            fast_max_output_tokens=800,
        )
    )
    budget = runtime.token_budget(
        route=_route(ModelTier.FAST),
        role="answer",
        base_input_tokens=12000,
        base_output_tokens=2400,
    )
    assert budget.max_input_tokens == 6000
    assert budget.max_output_tokens == 800


def test_standard_route_uses_intermediate_budget() -> None:
    runtime = AdaptiveAgentRuntime(
        AdaptiveAgentRuntimeConfig(
            standard_max_input_tokens=9000,
            standard_max_output_tokens=1200,
        )
    )
    budget = runtime.token_budget(
        route=_route(ModelTier.STANDARD),
        role="answer",
        base_input_tokens=12000,
        base_output_tokens=2400,
    )
    assert budget.max_input_tokens == 9000
    assert budget.max_output_tokens == 1200


def test_deep_emergency_writer_keeps_full_configured_budget() -> None:
    runtime = AdaptiveAgentRuntime(AdaptiveAgentRuntimeConfig())
    budget = runtime.token_budget(
        route=_route(ModelTier.DEEP),
        role="answer",
        base_input_tokens=12000,
        base_output_tokens=2400,
    )
    assert budget.max_input_tokens == 12000
    assert budget.max_output_tokens == 2400


def test_verifier_budget_is_bounded_but_not_bypassed() -> None:
    runtime = AdaptiveAgentRuntime(
        AdaptiveAgentRuntimeConfig(verifier_fast_max_output_tokens=600)
    )
    budget = runtime.token_budget(
        route=_route(ModelTier.FAST),
        role="verifier",
        base_input_tokens=12000,
        base_output_tokens=1800,
    )
    assert budget.max_input_tokens <= 7000
    assert budget.max_output_tokens == 600


def test_missing_adaptive_route_preserves_legacy_budget() -> None:
    runtime = AdaptiveAgentRuntime(
        AdaptiveAgentRuntimeConfig(
            standard_max_input_tokens=1000,
            standard_max_output_tokens=100,
        )
    )
    budget = runtime.token_budget(
        route=None,
        role="answer",
        base_input_tokens=12000,
        base_output_tokens=2400,
    )
    assert budget.max_input_tokens == 12000
    assert budget.max_output_tokens == 2400


def test_real_kev_cannot_enter_enforced_mode_without_validated_calibration() -> None:
    runtime = AdaptiveAgentRuntime(
        AdaptiveAgentRuntimeConfig(
            mode="enforced",
            kev_base_url="http://kev:9000",
            kev_calibration_status="unvalidated",
            kev_calibration_version=None,
        )
    )
    assert runtime.mode == "shadow"
    assert runtime.kev.config.mode == "shadow"


def test_real_kev_can_enter_enforced_mode_with_versioned_validated_calibration() -> None:
    runtime = AdaptiveAgentRuntime(
        AdaptiveAgentRuntimeConfig(
            mode="enforced",
            kev_base_url="http://kev:9000",
            kev_calibration_status="validated",
            kev_calibration_version="kev-medguard-2026-09-28-v1",
        )
    )
    assert runtime.mode == "enforced"
    assert runtime.kev.config.mode == "enforced"
