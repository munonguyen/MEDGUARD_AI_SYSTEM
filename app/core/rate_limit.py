"""Tenant-aware request rate limiting with development and Redis backends."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from time import time
from typing import Any, Protocol

from app.core.config import settings


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_after_seconds: int
    available: bool = True


class RateLimiter(Protocol):
    backend_name: str
    is_distributed: bool

    def check(self, identity: str, bucket: str) -> RateLimitDecision: ...

    def clear(self) -> None: ...


@dataclass
class _Window:
    count: int
    expires_at: float


class InMemoryRateLimiter:
    """Thread-safe development limiter with bounded, expiring state."""

    backend_name = "memory"
    is_distributed = False

    def __init__(
        self,
        limit: int,
        window_seconds: int,
        *,
        clock: Callable[[], float] = time,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._lock = Lock()
        self._windows: dict[tuple[str, str], _Window] = {}

    def check(self, identity: str, bucket: str) -> RateLimitDecision:
        now = self._clock()
        key = (identity, bucket)
        with self._lock:
            expired = [entry for entry, value in self._windows.items() if value.expires_at <= now]
            for entry in expired:
                self._windows.pop(entry, None)
            window = self._windows.get(key)
            if window is None or window.expires_at <= now:
                window = _Window(count=0, expires_at=now + self.window_seconds)
                self._windows[key] = window
            window.count += 1
            remaining = max(0, self.limit - window.count)
            reset_after = max(1, int(window.expires_at - now + 0.999))
            return RateLimitDecision(
                allowed=window.count <= self.limit,
                limit=self.limit,
                remaining=remaining,
                reset_after_seconds=reset_after,
            )

    def clear(self) -> None:
        with self._lock:
            self._windows.clear()


class RedisRateLimiter:
    """Atomic Redis limiter shared across API replicas."""

    backend_name = "redis"
    is_distributed = True
    _CHECK_SCRIPT = """
        local current = redis.call('INCR', KEYS[1])
        if current == 1 then
            redis.call('EXPIRE', KEYS[1], ARGV[1])
        end
        local ttl = redis.call('TTL', KEYS[1])
        return {current, ttl}
    """

    def __init__(
        self,
        redis_url: str,
        limit: int,
        window_seconds: int,
        *,
        client: Any | None = None,
    ) -> None:
        self.redis_url = redis_url
        self.limit = limit
        self.window_seconds = window_seconds
        self._client = client
        if client is None:
            self._init_client()

    def _init_client(self) -> None:
        try:
            import redis

            client = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
            self._client = client
        except Exception:
            self._client = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def healthcheck(self) -> bool:
        if self._client is None:
            self._init_client()
        try:
            return bool(self._client and self._client.ping())
        except Exception:
            self._client = None
            return False

    def check(self, identity: str, bucket: str) -> RateLimitDecision:
        if self._client is None:
            return RateLimitDecision(False, self.limit, 0, 1, available=False)
        digest = sha256(f"{identity}:{bucket}".encode("utf-8")).hexdigest()
        key = f"{settings.queue_name}:rate-limit:{digest}"
        try:
            count, ttl = self._client.eval(
                self._CHECK_SCRIPT,
                1,
                key,
                self.window_seconds,
            )
        except Exception:
            self._client = None
            return RateLimitDecision(False, self.limit, 0, 1, available=False)
        current = int(count)
        reset_after = max(1, int(ttl) if int(ttl) > 0 else self.window_seconds)
        return RateLimitDecision(
            allowed=current <= self.limit,
            limit=self.limit,
            remaining=max(0, self.limit - current),
            reset_after_seconds=reset_after,
        )

    def clear(self) -> None:
        raise RuntimeError("Refusing to clear distributed rate-limit state")


class RateLimitManager:
    def __init__(
        self,
        *,
        environment: str = settings.environment,
        enabled: bool = settings.rate_limit_enabled,
        redis_url: str | None = settings.redis_url,
        limit: int = settings.rate_limit_requests,
        window_seconds: int = settings.rate_limit_window_seconds,
        backend: RateLimiter | None = None,
    ) -> None:
        self.environment = environment.lower()
        self.enabled = enabled
        self.limit = limit
        self._memory = InMemoryRateLimiter(limit, window_seconds)
        self._redis = RedisRateLimiter(redis_url, limit, window_seconds) if redis_url else None
        self._injected_backend = backend

    @property
    def backend(self) -> RateLimiter:
        if self._injected_backend is not None:
            return self._injected_backend
        if self._redis and self._redis.is_connected:
            return self._redis
        return self._memory

    @property
    def backend_name(self) -> str:
        if not self.enabled:
            return "disabled"
        if self.environment == "production" and not self.is_distributed:
            return "unavailable"
        return self.backend.backend_name

    @property
    def is_distributed(self) -> bool:
        return bool(self.enabled and self.backend.is_distributed)

    @property
    def is_healthy(self) -> bool:
        if not self.enabled:
            return False
        if self._injected_backend is not None:
            return True
        if self._redis:
            return self._redis.healthcheck()
        return self.environment != "production"

    def check(self, identity: str, bucket: str) -> RateLimitDecision:
        if not self.enabled:
            return RateLimitDecision(True, 0, 0, 0)
        if self.environment == "production" and not self.is_distributed:
            return RateLimitDecision(
                False,
                self.limit,
                0,
                1,
                available=False,
            )
        return self.backend.check(identity, bucket)

    def clear(self) -> None:
        if not self.backend.is_distributed:
            self.backend.clear()


rate_limiter = RateLimitManager()
