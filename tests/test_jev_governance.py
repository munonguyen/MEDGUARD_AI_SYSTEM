"""Unit Tests for Jev Governance: Circuit Breaker, Timeout Budget & Caching."""

import time
import pytest
from app.models.jev import DecisionState, JevDecision
from app.services.jev_governance import (
    CircuitState,
    DecisionStateCache,
    JevCircuitBreaker,
    execute_jev_governed,
    jev_circuit_breaker,
    jev_decision_cache,
)


def test_decision_state_cache():
    cache = DecisionStateCache(ttl_seconds=1.0)
    decision = JevDecision(
        action="EMERGENCY_NOW",
        confidence=0.99,
        allow_home_monitoring=False,
        require_human_review=False,
        triage_recommendation="EMERGENCY",
    )
    cache.put("test_hash_1", decision)
    assert cache.get("test_hash_1") is not None
    assert cache.get("non_existent") is None

    # Test TTL expiration
    time.sleep(1.1)
    assert cache.get("test_hash_1") is None


def test_circuit_breaker_transition():
    cb = JevCircuitBreaker(
        failure_threshold=0.05,
        p95_latency_threshold_ms=200.0,
        recovery_time_sec=1.0,
        min_samples=5,
    )
    assert cb.allow_request() is True

    # Record 5 failures
    for _ in range(5):
        cb.record_failure()

    # Breaker should now be OPEN
    assert cb.stats.state == CircuitState.OPEN
    assert cb.allow_request() is False

    # Wait for recovery period
    time.sleep(1.1)
    assert cb.allow_request() is True
    assert cb.stats.state == CircuitState.HALF_OPEN

    # Record success -> transitions back to CLOSED
    cb.record_success(50.0)
    assert cb.stats.state == CircuitState.CLOSED


def test_execute_jev_governed_cache_hit():
    jev_decision_cache.clear()
    state = DecisionState(
        triage_floor="ROUTINE",
        reasoner_triage="ROUTINE",
        risk_features=(),
    )
    # First execution -> computes & caches
    d1 = execute_jev_governed(state)
    assert d1.cached is False

    # Second execution -> hits cache
    d2 = execute_jev_governed(state)
    assert d2.cached is True
    assert d2.action == d1.action


def test_execute_jev_governed_timeout_fallback():
    jev_decision_cache.clear()
    state = DecisionState(
        triage_floor="URGENT",
        reasoner_triage="URGENT",
    )

    def slow_engine(s):
        time.sleep(0.3)
        return JevDecision(
            action="SAME_DAY_EVAL",
            confidence=0.9,
            allow_home_monitoring=False,
            require_human_review=False,
            triage_recommendation="URGENT",
        )

    # Call with 50ms budget, engine takes 300ms -> triggers timeout fallback
    d = execute_jev_governed(state, timeout_ms=50.0, engine_fn=slow_engine)
    assert d.timeout_fallback is True
    assert d.triage_recommendation == "URGENT"
    assert d.allow_home_monitoring is False
