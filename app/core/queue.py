"""Reliable job queue adapters with pending, processing and dead-letter states."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from threading import Lock
from time import time
from typing import Any

from app.core.config import settings


@dataclass
class QueueMessage:
    job_id: str
    tenant_id: str
    payload: dict[str, Any]
    priority: int = 0
    enqueued_at: float = field(default_factory=time)
    attempts: int = 0
    claimed_at: float | None = None
    failure_reason: str | None = None
    receipt: str | None = field(default=None, repr=False)

    def serialized(self) -> str:
        data = asdict(self)
        data.pop("receipt", None)
        return json.dumps(data, separators=(",", ":"), sort_keys=True)

    @classmethod
    def from_serialized(cls, raw: str | bytes) -> "QueueMessage":
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        return cls(
            job_id=data["job_id"],
            tenant_id=data["tenant_id"],
            payload=data.get("payload", {}),
            priority=int(data.get("priority", 0)),
            enqueued_at=float(data.get("enqueued_at", time())),
            attempts=int(data.get("attempts", 0)),
            claimed_at=data.get("claimed_at"),
            failure_reason=data.get("failure_reason"),
            receipt=raw,
        )


class InMemoryJobQueue:
    """Thread-safe queue for local development with production-like states."""

    def __init__(self, max_attempts: int = 3) -> None:
        self.max_attempts = max_attempts
        self._lock = Lock()
        self._pending: list[QueueMessage] = []
        self._in_flight: dict[str, QueueMessage] = {}
        self._dead_letter: list[QueueMessage] = []

    def enqueue(
        self,
        tenant_id: str,
        job_id: str,
        payload: dict[str, Any],
        priority: int = 0,
    ) -> str:
        message = QueueMessage(
            job_id=job_id,
            tenant_id=tenant_id,
            payload=payload,
            priority=priority,
        )
        with self._lock:
            self._pending.append(message)
            self._pending.sort(key=lambda item: item.priority, reverse=True)
        return job_id

    def dequeue(self, timeout_seconds: float = 0.5) -> QueueMessage | None:
        del timeout_seconds
        with self._lock:
            if not self._pending:
                return None
            message = self._pending.pop(0)
            message.attempts += 1
            message.claimed_at = time()
            self._in_flight[message.job_id] = message
            return message

    def ack(self, job_id: str) -> None:
        with self._lock:
            self._in_flight.pop(job_id, None)

    def fail(self, job_id: str, reason: str, requeue: bool = False) -> None:
        with self._lock:
            message = self._in_flight.pop(job_id, None)
            if message is None:
                return
            message.failure_reason = reason
            message.claimed_at = None
            if requeue and message.attempts < self.max_attempts:
                self._pending.append(message)
                self._pending.sort(key=lambda item: item.priority, reverse=True)
            else:
                self._dead_letter.append(message)

    def reclaim_stale(self, visibility_timeout_seconds: float) -> int:
        cutoff = time() - visibility_timeout_seconds
        with self._lock:
            stale_ids = [
                job_id
                for job_id, message in self._in_flight.items()
                if message.claimed_at is not None and message.claimed_at <= cutoff
            ]
            for job_id in stale_ids:
                message = self._in_flight.pop(job_id)
                message.claimed_at = None
                if message.attempts < self.max_attempts:
                    self._pending.append(message)
                else:
                    message.failure_reason = "visibility_timeout_exceeded"
                    self._dead_letter.append(message)
            self._pending.sort(key=lambda item: item.priority, reverse=True)
            return len(stale_ids)

    def queue_depth(self, tenant_id: str | None = None) -> int:
        with self._lock:
            if tenant_id is None:
                return len(self._pending)
            return sum(1 for message in self._pending if message.tenant_id == tenant_id)

    def processing_depth(self) -> int:
        with self._lock:
            return len(self._in_flight)

    def dead_letter_depth(self) -> int:
        with self._lock:
            return len(self._dead_letter)

    def clear(self) -> None:
        with self._lock:
            self._pending.clear()
            self._in_flight.clear()
            self._dead_letter.clear()


class RedisJobQueue:
    """Redis 6.2+ queue using BLMOVE for atomic pending-to-processing claims."""

    _MOVE_IF_PRESENT_SCRIPT = """
        local removed = redis.call('LREM', KEYS[1], 1, ARGV[1])
        if removed == 1 then
            redis.call('LPUSH', KEYS[2], ARGV[2])
        end
        return removed
    """

    def __init__(
        self,
        redis_url: str,
        queue_name: str = "medguard_jobs",
        *,
        max_attempts: int = 3,
        client: Any | None = None,
    ) -> None:
        self.redis_url = redis_url
        self.queue_name = queue_name
        self.max_attempts = max_attempts
        self.pending_key = f"{queue_name}:pending"
        self.processing_key = f"{queue_name}:processing"
        self.dead_letter_key = f"{queue_name}:dead-letter"
        self._client = client
        self._in_flight: dict[str, str] = {}
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
        if not self._client:
            self._init_client()
            if not self._client:
                return False
        try:
            return bool(self._client.ping())
        except Exception:
            self._client = None
            return False

    def enqueue(
        self,
        tenant_id: str,
        job_id: str,
        payload: dict[str, Any],
        priority: int = 0,
    ) -> str:
        if not self._client:
            raise RuntimeError("Redis client is not available")
        message = QueueMessage(
            job_id=job_id,
            tenant_id=tenant_id,
            payload=payload,
            priority=priority,
        )
        self._client.lpush(self.pending_key, message.serialized())
        return job_id

    def dequeue(self, timeout_seconds: float = 0.5) -> QueueMessage | None:
        if not self._client:
            return None
        raw = self._client.execute_command(
            "BLMOVE",
            self.pending_key,
            self.processing_key,
            "RIGHT",
            "LEFT",
            max(0, timeout_seconds),
        )
        if raw is None:
            return None

        message = QueueMessage.from_serialized(raw)
        message.attempts += 1
        message.claimed_at = time()
        claimed_raw = message.serialized()
        replaced = self._client.eval(
            self._MOVE_IF_PRESENT_SCRIPT,
            2,
            self.processing_key,
            self.processing_key,
            raw,
            claimed_raw,
        )
        if int(replaced) != 1:
            return None
        message.receipt = claimed_raw
        self._in_flight[message.job_id] = claimed_raw
        return message

    def ack(self, job_id: str) -> None:
        if not self._client:
            return
        receipt = self._in_flight.pop(job_id, None)
        if receipt:
            self._client.lrem(self.processing_key, 1, receipt)

    def fail(self, job_id: str, reason: str, requeue: bool = False) -> None:
        if not self._client:
            return
        receipt = self._in_flight.pop(job_id, None)
        if not receipt:
            return
        message = QueueMessage.from_serialized(receipt)
        message.failure_reason = reason
        message.claimed_at = None
        destination = (
            self.pending_key
            if requeue and message.attempts < self.max_attempts
            else self.dead_letter_key
        )
        self._client.eval(
            self._MOVE_IF_PRESENT_SCRIPT,
            2,
            self.processing_key,
            destination,
            receipt,
            message.serialized(),
        )

    def reclaim_stale(self, visibility_timeout_seconds: float) -> int:
        if not self._client:
            return 0
        cutoff = time() - visibility_timeout_seconds
        reclaimed = 0
        for raw in self._client.lrange(self.processing_key, 0, -1):
            message = QueueMessage.from_serialized(raw)
            claimed_at = float(message.claimed_at or message.enqueued_at)
            if claimed_at > cutoff:
                continue
            message.claimed_at = None
            if message.attempts >= self.max_attempts:
                message.failure_reason = "visibility_timeout_exceeded"
                destination = self.dead_letter_key
            else:
                destination = self.pending_key
            moved = self._client.eval(
                self._MOVE_IF_PRESENT_SCRIPT,
                2,
                self.processing_key,
                destination,
                raw,
                message.serialized(),
            )
            if int(moved) == 1:
                reclaimed += 1
                self._in_flight.pop(message.job_id, None)
        return reclaimed

    def queue_depth(self, tenant_id: str | None = None) -> int:
        if not self._client:
            return 0
        if tenant_id is None:
            return int(self._client.llen(self.pending_key))
        return sum(
            1
            for raw in self._client.lrange(self.pending_key, 0, -1)
            if QueueMessage.from_serialized(raw).tenant_id == tenant_id
        )

    def processing_depth(self) -> int:
        return int(self._client.llen(self.processing_key)) if self._client else 0

    def dead_letter_depth(self) -> int:
        return int(self._client.llen(self.dead_letter_key)) if self._client else 0

    def clear(self) -> None:
        if self._client:
            self._client.delete(self.pending_key, self.processing_key, self.dead_letter_key)


class QueueManager:
    def __init__(self) -> None:
        self._in_memory = InMemoryJobQueue(settings.queue_max_attempts)
        self._redis: RedisJobQueue | None = None
        if settings.redis_url:
            self._redis = RedisJobQueue(
                settings.redis_url,
                settings.queue_name,
                max_attempts=settings.queue_max_attempts,
            )

    @property
    def backend(self) -> InMemoryJobQueue | RedisJobQueue:
        if self._redis and self._redis.is_connected:
            return self._redis
        return self._in_memory

    @property
    def backend_name(self) -> str:
        return "redis" if isinstance(self.backend, RedisJobQueue) else "memory"

    @property
    def is_durable(self) -> bool:
        return isinstance(self.backend, RedisJobQueue)

    @property
    def is_healthy(self) -> bool:
        return bool(self._redis and self._redis.healthcheck())

    def _backend_for_work(self) -> InMemoryJobQueue | RedisJobQueue:
        if settings.environment.lower() == "production" and not self.is_healthy:
            raise RuntimeError("A healthy Redis queue is required in production")
        return self.backend

    def enqueue(
        self,
        tenant_id: str,
        job_id: str,
        payload: dict[str, Any],
        priority: int = 0,
    ) -> str:
        return self._backend_for_work().enqueue(tenant_id, job_id, payload, priority)

    def dequeue(self, timeout_seconds: float = 0.5) -> QueueMessage | None:
        return self._backend_for_work().dequeue(timeout_seconds)

    def ack(self, job_id: str) -> None:
        self._backend_for_work().ack(job_id)

    def fail(self, job_id: str, reason: str, requeue: bool = False) -> None:
        self._backend_for_work().fail(job_id, reason, requeue)

    def reclaim_stale(self, visibility_timeout_seconds: float) -> int:
        return self._backend_for_work().reclaim_stale(visibility_timeout_seconds)

    def queue_depth(self, tenant_id: str | None = None) -> int:
        return self.backend.queue_depth(tenant_id)

    def processing_depth(self) -> int:
        return self.backend.processing_depth()

    def dead_letter_depth(self) -> int:
        return self.backend.dead_letter_depth()

    def clear(self) -> None:
        if isinstance(self.backend, RedisJobQueue):
            raise RuntimeError("Refusing to clear a Redis queue through the application API")
        self.backend.clear()


job_queue = QueueManager()
