"""Clinical and Systems Observability Metrics Exporter for MedGuard AI.

Collects and reports:
1. Triage Distribution (EMERGENCY, URGENT, ROUTINE counts)
2. Jev Engine Metrics: invocation count, invocation rate %, timeouts, cache hit rate %
3. Latency Metrics: P50, P90, P95, P99 across Fast Path, Review Path, Critical Path
4. Circuit Breaker States: CLOSED, OPEN, HALF-OPEN
5. System Error Rate and DLQ count
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
import time
from typing import Any


@dataclass
class ObservabilitySnapshot:
    uptime_seconds: float
    total_triage_requests: int
    triage_distribution: dict[str, int]
    jev_invocations: int
    jev_timeouts: int
    jev_cache_hits: int
    jev_invocation_rate_pct: float
    jev_cache_hit_rate_pct: float
    circuit_breaker_state: str
    latency_p50_ms: float
    latency_p90_ms: float
    latency_p95_ms: float
    latency_p99_ms: float


class MetricsCollector:
    def __init__(self) -> None:
        self._lock = RLock()
        self._start_time = time.time()
        self.triage_counts: dict[str, int] = {"EMERGENCY": 0, "URGENT": 0, "ROUTINE": 0}
        self.jev_invocations = 0
        self.jev_timeouts = 0
        self.jev_cache_hits = 0
        self.total_requests = 0
        self.latencies_ms: list[float] = []

    def record_triage(
        self,
        triage: str,
        latency_ms: float,
        jev_invoked: bool = False,
        jev_cached: bool = False,
        jev_timeout: bool = False,
    ) -> None:
        with self._lock:
            self.total_requests += 1
            self.triage_counts[triage] = self.triage_counts.get(triage, 0) + 1
            self.latencies_ms.append(latency_ms)
            if len(self.latencies_ms) > 10000:
                self.latencies_ms = self.latencies_ms[-5000:]

            if jev_invoked:
                self.jev_invocations += 1
            if jev_cached:
                self.jev_cache_hits += 1
            if jev_timeout:
                self.jev_timeouts += 1

    def get_snapshot(self) -> ObservabilitySnapshot:
        with self._lock:
            uptime = time.time() - self._start_time
            total = self.total_requests
            inv_rate = (self.jev_invocations / total * 100.0) if total > 0 else 0.0
            cache_rate = (self.jev_cache_hits / self.jev_invocations * 100.0) if self.jev_invocations > 0 else 0.0

            lats = sorted(self.latencies_ms)
            if not lats:
                p50 = p90 = p95 = p99 = 0.0
            else:
                n = len(lats)
                p50 = lats[int(n * 0.50)]
                p90 = lats[int(n * 0.90)]
                p95 = lats[int(n * 0.95)]
                p99 = lats[int(n * 0.99)]

            # Check circuit breaker from model_circuit
            from app.services.circuit import model_circuit
            cb_state = "CLOSED"
            if hasattr(model_circuit, "is_open") and model_circuit.is_open("tri-gate-jev"):
                cb_state = "OPEN"

            return ObservabilitySnapshot(
                uptime_seconds=round(uptime, 1),
                total_triage_requests=total,
                triage_distribution=dict(self.triage_counts),
                jev_invocations=self.jev_invocations,
                jev_timeouts=self.jev_timeouts,
                jev_cache_hits=self.jev_cache_hits,
                jev_invocation_rate_pct=round(inv_rate, 2),
                jev_cache_hit_rate_pct=round(cache_rate, 2),
                circuit_breaker_state=cb_state,
                latency_p50_ms=round(p50, 2),
                latency_p90_ms=round(p90, 2),
                latency_p95_ms=round(p95, 2),
                latency_p99_ms=round(p99, 2),
            )


# Global singleton
metrics_collector = MetricsCollector()
