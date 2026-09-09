from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from threading import RLock
from time import monotonic

from app.core.config import settings


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitSnapshot:
    state: CircuitState
    failure_count: int
    total_requests: int
    error_rate: float
    latency_ms: int = 0


class CircuitBreaker:
    """Small process-local breaker for optional model/provider calls.

    The API layer should use ``allow_request`` before calling an external
    model. OPEN means the caller must take its deterministic/manual fallback.
    """

    def __init__(self, *, error_threshold: float | None = None, min_requests: int | None = None) -> None:
        self._lock = RLock()
        self.failure_count = 0
        self.total_requests = 0
        self.opened_at: float | None = None
        self.error_threshold = settings.circuit_error_threshold if error_threshold is None else error_threshold
        self.min_requests = settings.circuit_min_requests if min_requests is None else min_requests

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self.opened_at is None:
                return CircuitState.CLOSED
            if monotonic() - self.opened_at >= settings.circuit_timeout_ms / 1000:
                return CircuitState.HALF_OPEN
            return CircuitState.OPEN

    def allow_request(self) -> bool:
        current = self.state
        return current in {CircuitState.CLOSED, CircuitState.HALF_OPEN}

    def record_success(self) -> None:
        with self._lock:
            self.total_requests += 1
            self.failure_count = 0
            self.opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self.total_requests += 1
            self.failure_count += 1
            error_rate = self.failure_count / max(self.total_requests, 1)
            if self.total_requests >= self.min_requests and error_rate >= self.error_threshold:
                self.opened_at = monotonic()

    def snapshot(self) -> CircuitSnapshot:
        with self._lock:
            return CircuitSnapshot(
                state=self.state,
                failure_count=self.failure_count,
                total_requests=self.total_requests,
                error_rate=round(self.failure_count / max(self.total_requests, 1), 4),
            )

    def reset(self) -> None:
        with self._lock:
            self.failure_count = 0
            self.total_requests = 0
            self.opened_at = None


model_circuit = CircuitBreaker()
