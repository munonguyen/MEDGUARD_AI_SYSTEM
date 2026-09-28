from __future__ import annotations

from app.services.adaptive_agent_runtime import AdaptiveAgentRuntime, AdaptiveAgentRuntimeConfig
from app.services.readiness import adaptive_routing_readiness


def test_shadow_mode_is_a_valid_controlled_readiness_state() -> None:
    runtime = AdaptiveAgentRuntime(
        AdaptiveAgentRuntimeConfig(
            mode="shadow",
            kev_base_url="http://kev:9000",
            kev_calibration_status="unvalidated",
        )
    )
    status, detail = adaptive_routing_readiness(runtime)
    assert status == "pass"
    assert "shadow mode" in detail


def test_enforced_mode_without_kev_url_fails_readiness() -> None:
    runtime = AdaptiveAgentRuntime(
        AdaptiveAgentRuntimeConfig(
            mode="enforced",
            kev_base_url=None,
            kev_calibration_status="validated",
            kev_calibration_version="cal-v1",
        )
    )
    status, detail = adaptive_routing_readiness(runtime)
    assert status == "fail"
    assert "MEDGUARD_KEV_URL" in detail


def test_enforced_mode_with_uncalibrated_kev_fails_readiness() -> None:
    runtime = AdaptiveAgentRuntime(
        AdaptiveAgentRuntimeConfig(
            mode="enforced",
            kev_base_url="http://kev:9000",
            kev_calibration_status="unvalidated",
            kev_calibration_version=None,
        )
    )
    status, detail = adaptive_routing_readiness(runtime)
    assert runtime.mode == "shadow"
    assert status == "fail"
    assert "calibration" in detail.lower()


def test_enforced_mode_with_validated_versioned_kev_passes_readiness() -> None:
    runtime = AdaptiveAgentRuntime(
        AdaptiveAgentRuntimeConfig(
            mode="enforced",
            kev_base_url="http://kev:9000",
            kev_calibration_status="validated",
            kev_calibration_version="kev-medguard-v1",
        )
    )
    status, detail = adaptive_routing_readiness(runtime)
    assert runtime.mode == "enforced"
    assert status == "pass"
    assert "versioned validated calibration" in detail


def test_invalid_adaptive_mode_fails_readiness() -> None:
    runtime = AdaptiveAgentRuntime(AdaptiveAgentRuntimeConfig(mode="banana"))
    status, detail = adaptive_routing_readiness(runtime)
    assert runtime.mode == "shadow"
    assert status == "fail"
    assert "invalid adaptive routing mode" in detail
