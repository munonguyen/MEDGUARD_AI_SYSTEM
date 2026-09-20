"""Governance, Circuit Breaker, Timeout Budget & Caching for Gate 3 (Jev).

Design Principles:
1. Circuit Breaker: If Jev latency spikes (P95 > 250ms) or error rate exceeds 5%,
   the circuit trips to OPEN, instantly bypassing Jev to keep 2-gate throughput stable.
2. Timeout Budget: Strict per-request SLA (default 250ms). If exceeded, falls back
   gracefully to max(deterministic_floor, reasoner) without blocking user responses.
3. Abstract Decision State Cache: Caches Jev decisions indexed by state_hash.
   Only caches pure clinical abstraction tuples, strictly avoiding PHI leakage.
"""

from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from enum import Enum
import logging
from threading import RLock
import time
from typing import Any, Callable

from app.models.jev import DecisionState, JevDecision
from app.services.jev_engine import evaluate_jev_decision

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"      # Healthy, executing Jev
    OPEN = "OPEN"          # Unhealthy, bypassing Jev
    HALF_OPEN = "HALF_OPEN"# Trialing recovery


@dataclass
class CircuitBreakerStats:
    total_calls: int = 0
    error_count: int = 0
    timeout_count: int = 0
    latencies_ms: deque[float] = field(default_factory=lambda: deque(maxlen=100))
    state: CircuitState = CircuitState.CLOSED
    last_state_change: float = field(default_factory=time.time)


class JevCircuitBreaker:
    """Rolling window circuit breaker for Gate 3 (Jev)."""

    def __init__(
        self,
        failure_threshold: float = 0.05,
        p95_latency_threshold_ms: float = 250.0,
        recovery_time_sec: float = 30.0,
        min_samples: int = 20,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.p95_threshold_ms = p95_latency_threshold_ms
        self.recovery_time_sec = recovery_time_sec
        self.min_samples = min_samples
        self.stats = CircuitBreakerStats()
        self._lock = RLock()

    def allow_request(self) -> bool:
        with self._lock:
            now = time.time()
            if self.stats.state == CircuitState.OPEN:
                if now - self.stats.last_state_change >= self.recovery_time_sec:
                    self.stats.state = CircuitState.HALF_OPEN
                    self.stats.last_state_change = now
                    logger.info("Jev CircuitBreaker transitioned from OPEN to HALF_OPEN")
                    return True
                return False
            return True

    def record_success(self, latency_ms: float) -> None:
        with self._lock:
            self.stats.total_calls += 1
            self.stats.latencies_ms.append(latency_ms)
            if self.stats.state == CircuitState.HALF_OPEN:
                self.stats.state = CircuitState.CLOSED
                self.stats.error_count = 0
                self.stats.timeout_count = 0
                self.stats.last_state_change = time.time()
                logger.info("Jev CircuitBreaker recovered to CLOSED")
            self._evaluate_health()

    def record_failure(self, is_timeout: bool = False) -> None:
        with self._lock:
            self.stats.total_calls += 1
            if is_timeout:
                self.stats.timeout_count += 1
            else:
                self.stats.error_count += 1
            self._evaluate_health()

    def _evaluate_health(self) -> None:
        if self.stats.total_calls < self.min_samples:
            return

        total_errs = self.stats.error_count + self.stats.timeout_count
        error_rate = total_errs / max(self.stats.total_calls, 1)

        if self.stats.latencies_ms:
            sorted_lat = sorted(self.stats.latencies_ms)
            p95_idx = int(0.95 * len(sorted_lat))
            p95_lat = sorted_lat[min(p95_idx, len(sorted_lat) - 1)]
        else:
            p95_lat = 0.0

        if error_rate >= self.failure_threshold or p95_lat >= self.p95_threshold_ms:
            if self.stats.state != CircuitState.OPEN:
                self.stats.state = CircuitState.OPEN
                self.stats.last_state_change = time.time()
                logger.warning(
                    f"Jev CircuitBreaker TRIPPED to OPEN! err_rate={error_rate:.2%}, p95={p95_lat:.1f}ms"
                )

    def reset(self) -> None:
        with self._lock:
            self.stats = CircuitBreakerStats()


class DecisionStateCache:
    """Thread-safe TTL in-memory cache for abstract DecisionState hashes."""

    def __init__(self, ttl_seconds: float = 300.0, max_size: int = 1000) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: dict[str, tuple[float, JevDecision]] = {}
        self._lock = RLock()

    def get(self, state_hash: str) -> JevDecision | None:
        with self._lock:
            entry = self._cache.get(state_hash)
            if not entry:
                return None
            ts, decision = entry
            if time.time() - ts > self.ttl_seconds:
                del self._cache[state_hash]
                return None
            return decision

    def put(self, state_hash: str, decision: JevDecision) -> None:
        with self._lock:
            if len(self._cache) >= self.max_size:
                # Evict oldest 20%
                oldest_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k][0])[: self.max_size // 5]
                for k in oldest_keys:
                    self._cache.pop(k, None)
            self._cache[state_hash] = (time.time(), decision)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


# Global Singleton Instances
jev_circuit_breaker = JevCircuitBreaker()
jev_decision_cache = DecisionStateCache()
_JEV_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="medguard-jev")


def execute_jev_governed(
    state: DecisionState,
    timeout_ms: float = 250.0,
    *,
    engine_fn: Callable[[DecisionState], JevDecision] = evaluate_jev_decision,
) -> JevDecision:
    """Execute Gate 3 (Jev) with cache lookup, circuit breaking, and timeout enforcement."""
    s_hash = state.state_hash()

    # 1. Cache Check
    cached_val = jev_decision_cache.get(s_hash)
    if cached_val is not None:
        return JevDecision(
            action=cached_val.action,
            confidence=cached_val.confidence,
            allow_home_monitoring=cached_val.allow_home_monitoring,
            require_human_review=cached_val.require_human_review,
            triage_recommendation=cached_val.triage_recommendation,
            policy_rules_triggered=cached_val.policy_rules_triggered,
            latency_ms=0.1,
            source="jev_cache",
            cached=True,
        )

    # 2. Circuit Breaker Check
    if not jev_circuit_breaker.allow_request():
        # Fail-Open / Bypass Jev gracefully
        fallback_action = "EMERGENCY_NOW" if state.triage_floor == "EMERGENCY" else (
            "SAME_DAY_EVAL" if state.triage_floor == "URGENT" or state.reasoner_triage == "URGENT" else "SELF_CARE"
        )
        return JevDecision(
            action=fallback_action,
            confidence=state.confidence,
            allow_home_monitoring=(fallback_action == "SELF_CARE"),
            require_human_review=False,
            triage_recommendation=state.reasoner_triage,
            policy_rules_triggered=("circuit_breaker_bypassed_fallback",),
            latency_ms=0.1,
            source="circuit_breaker_bypass",
            circuit_breaker_bypassed=True,
        )

    # 3. Execution with Timeout Budget
    t0 = time.perf_counter()
    try:
        future = _JEV_POOL.submit(engine_fn, state)
        decision = future.result(timeout=timeout_ms / 1000.0)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        jev_circuit_breaker.record_success(elapsed_ms)
        jev_decision_cache.put(s_hash, decision)
        return decision

    except FutureTimeoutError:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        jev_circuit_breaker.record_failure(is_timeout=True)
        logger.warning(f"Jev timed out after {elapsed_ms:.1f}ms (budget={timeout_ms}ms); applying safety fallback.")

        fallback_action = "EMERGENCY_NOW" if state.triage_floor == "EMERGENCY" or state.reasoner_triage == "EMERGENCY" else (
            "SAME_DAY_EVAL" if state.triage_floor == "URGENT" or state.reasoner_triage == "URGENT" else "SELF_CARE"
        )
        return JevDecision(
            action=fallback_action,
            confidence=state.confidence,
            allow_home_monitoring=(fallback_action == "SELF_CARE"),
            require_human_review=False,
            triage_recommendation=state.reasoner_triage if state.triage_floor == "ROUTINE" else state.triage_floor,
            policy_rules_triggered=("jev_timeout_safety_floor",),
            latency_ms=round(elapsed_ms, 2),
            source="timeout_fallback",
            timeout_fallback=True,
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        jev_circuit_breaker.record_failure(is_timeout=False)
        logger.error(f"Jev execution error ({exc}); applying safety fallback.")

        return JevDecision(
            action="EMERGENCY_NOW" if state.triage_floor == "EMERGENCY" else "SAME_DAY_EVAL",
            confidence=0.70,
            allow_home_monitoring=False,
            require_human_review=True,
            triage_recommendation="URGENT" if state.triage_floor == "ROUTINE" else state.triage_floor,
            policy_rules_triggered=("jev_exception_fail_closed",),
            latency_ms=round(elapsed_ms, 2),
            source="exception_fallback",
        )
