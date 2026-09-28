from __future__ import annotations

from app.models.adaptive_routing import AdaptiveRouteDecision, ModelTier, SeverityAgent, SeverityChoice
from app.services.adaptive_agent_runtime import AdaptiveAgentRuntime, AdaptiveAgentRuntimeConfig


def _route(tier: ModelTier) -> AdaptiveRouteDecision:
    return AdaptiveRouteDecision(
        clinical_task="acute_symptom",
        resolved_severity="ROUTINE",
        agent=SeverityAgent.ROUTINE,
        model_tier=tier,
        kev_choice=SeverityChoice.ROUTINE,
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
