"""Governance, circuit breaking, timeout budget and caching for Jev.

V14 keeps Jev fast and PHI-free while preserving its new authority boundary:
- cache/circuit/timeout wrappers must not promote an advisory decision into a
  disposition authority;
- an ``emergency_lock`` is preserved only when it originated from an existing
  deterministic emergency floor;
- failures return advisory signals and human-review hints instead of creating a
  new ROUTINE->URGENT escalation on their own.
"""

from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from enum import Enum
import logging
from threading import RLock
import time
from typing import Callable

from app.models.jev import DecisionState, JevDecision
from app.services.jev_engine import evaluate_jev_decision

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitBreakerStats:
    total_calls: int = 0
    error_count: int = 0
    timeout_count: int = 0
    latencies_ms: deque[float] = field(default_factory=lambda: deque(maxlen=100))
    state: CircuitState = CircuitState.CLOSED
    last_state_change: float = field(default_factory=time.time)


class JevCircuitBreaker:
    """Rolling-window circuit breaker for Jev."""

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
                    "Jev CircuitBreaker TRIPPED to OPEN! err_rate=%.2f%%, p95=%.1fms",
                    error_rate * 100.0,
                    p95_lat,
                )

    def reset(self) -> None:
        with self._lock:
            self.stats = CircuitBreakerStats()


class DecisionStateCache:
    """Thread-safe TTL cache for PHI-free DecisionState hashes."""

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
                oldest_keys = sorted(
                    self._cache.keys(), key=lambda key: self._cache[key][0]
                )[: self.max_size // 5]
                for key in oldest_keys:
                    self._cache.pop(key, None)
            self._cache[state_hash] = (time.time(), decision)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


jev_circuit_breaker = JevCircuitBreaker()
jev_decision_cache = DecisionStateCache()
_JEV_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="medguard-jev")


def _fallback_decision(
    state: DecisionState,
    *,
    rule: str,
    source: str,
    latency_ms: float = 0.1,
    require_human_review: bool = False,
    circuit_bypassed: bool = False,
    timed_out: bool = False,
) -> JevDecision:
    """Return a governance fallback without inventing new Jev authority."""
    if state.triage_floor == "EMERGENCY":
        action = "EMERGENCY_NOW"
        recommendation = "EMERGENCY"
        authority = "emergency_lock"
        allow_home = False
    elif state.reasoner_triage == "EMERGENCY":
        action = "EMERGENCY_NOW"
        recommendation = "EMERGENCY"
        authority = "advisory"
        allow_home = False
    elif state.triage_floor == "URGENT" or state.reasoner_triage == "URGENT":
        action = "SAME_DAY_EVAL"
        recommendation = "URGENT"
        authority = "advisory"
        allow_home = False
    else:
        action = "AMBIGUOUS_CLARIFY" if require_human_review else "SELF_CARE"
        recommendation = "ROUTINE"
        authority = "advisory"
        allow_home = not require_human_review

    return JevDecision(
        action=action,
        confidence=state.confidence if not require_human_review else min(state.confidence, 0.70),
        allow_home_monitoring=allow_home,
        require_human_review=require_human_review,
        triage_recommendation=recommendation,
        policy_rules_triggered=(rule,),
        clinical_insights=(rule,),
        suggested_clarifications=("review_jev_governance_failure",) if require_human_review else (),
        authority=authority,
        latency_ms=round(latency_ms, 2),
        source=source,
        circuit_breaker_bypassed=circuit_bypassed,
        timeout_fallback=timed_out,
    )


def execute_jev_governed(
    state: DecisionState,
    timeout_ms: float = 250.0,
    *,
    engine_fn: Callable[[DecisionState], JevDecision] = evaluate_jev_decision,
) -> JevDecision:
    """Execute Jev with cache, circuit breaking and a bounded timeout."""
    state_hash = state.state_hash()

    cached_val = jev_decision_cache.get(state_hash)
    if cached_val is not None:
        return JevDecision(
            action=cached_val.action,
            confidence=cached_val.confidence,
            allow_home_monitoring=cached_val.allow_home_monitoring,
            require_human_review=cached_val.require_human_review,
            triage_recommendation=cached_val.triage_recommendation,
            policy_rules_triggered=cached_val.policy_rules_triggered,
            clinical_insights=cached_val.clinical_insights,
            advisory_red_flags=cached_val.advisory_red_flags,
            suggested_clarifications=cached_val.suggested_clarifications,
            authority=cached_val.authority,
            latency_ms=0.1,
            source="jev_cache",
            cached=True,
        )

    if not jev_circuit_breaker.allow_request():
        return _fallback_decision(
            state,
            rule="circuit_breaker_bypassed_fallback",
            source="circuit_breaker_bypass",
            circuit_bypassed=True,
        )

    t0 = time.perf_counter()
    try:
        future = _JEV_POOL.submit(engine_fn, state)
        decision = future.result(timeout=timeout_ms / 1000.0)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        jev_circuit_breaker.record_success(elapsed_ms)
        jev_decision_cache.put(state_hash, decision)
        return decision
    except FutureTimeoutError:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        jev_circuit_breaker.record_failure(is_timeout=True)
        logger.warning(
            "Jev timed out after %.1fms (budget=%.1fms); returning advisory fallback.",
            elapsed_ms,
            timeout_ms,
        )
        return _fallback_decision(
            state,
            rule="jev_timeout_advisory_fallback",
            source="timeout_fallback",
            latency_ms=elapsed_ms,
            require_human_review=True,
            timed_out=True,
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        jev_circuit_breaker.record_failure(is_timeout=False)
        logger.error("Jev execution error (%s); returning advisory fallback.", exc)
        return _fallback_decision(
            state,
            rule="jev_exception_advisory_fallback",
            source="exception_fallback",
            latency_ms=elapsed_ms,
            require_human_review=True,
        )
