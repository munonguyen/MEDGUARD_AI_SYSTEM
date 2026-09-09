"""Tenant-scoped, durable idempotency response repository."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from threading import RLock
from time import time
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from pydantic import BaseModel

from app.core.context import RequestContext
from app.core.database import DatabaseManager, db_manager, decode_timestamp, encode_timestamp


@dataclass(frozen=True)
class IdempotencyEntry:
    payload_hash: str
    response: dict[str, Any]
    expires_at: float
    response_code: int = 200


class IdempotencyStore:
    def __init__(
        self,
        database: DatabaseManager = db_manager,
        ttl_seconds: int = 86_400,
        lease_seconds: int = 30,
    ) -> None:
        self.database = database
        self.ttl_seconds = ttl_seconds
        self.lease_seconds = lease_seconds
        self._lock = RLock()
        self.entries: dict[tuple[str, str, str], IdempotencyEntry] = {}

    def get(self, key: tuple[str, str, str]) -> IdempotencyEntry | None:
        tenant_id, endpoint, idempotency_key = key
        now = time()
        with self._lock:
            cached = self.entries.get(key)
            if cached and cached.expires_at > now:
                return cached
            self.entries.pop(key, None)

            with self.database.tenant_context(tenant_id) as session:
                rows = session.execute(
                    """
                    SELECT payload_hash, response_body, response_code, expires_at
                    FROM idempotency_records
                    WHERE tenant_id = ? AND endpoint = ? AND idempotency_key = ?
                    """,
                    (tenant_id, endpoint, idempotency_key),
                )
                if not rows:
                    return None
                row = rows[0]
                expires_at = decode_timestamp(row["expires_at"])
                if expires_at <= now:
                    session.execute(
                        """
                        DELETE FROM idempotency_records
                        WHERE tenant_id = ? AND endpoint = ? AND idempotency_key = ?
                        """,
                        (tenant_id, endpoint, idempotency_key),
                    )
                    return None

                raw_response = row["response_body"]
                response = raw_response if isinstance(raw_response, dict) else json.loads(raw_response)
                entry = IdempotencyEntry(
                    payload_hash=str(row["payload_hash"]),
                    response=response,
                    expires_at=expires_at,
                    response_code=int(row["response_code"]),
                )
                self.entries[key] = entry
                return entry

    def put(
        self,
        key: tuple[str, str, str],
        *,
        payload_hash: str,
        response: dict[str, Any],
    ) -> None:
        tenant_id, endpoint, idempotency_key = key
        created_at = time()
        expires_at = created_at + self.ttl_seconds
        entry = IdempotencyEntry(payload_hash, response, expires_at, 200)
        with self._lock:
            with self.database.tenant_context(tenant_id) as session:
                session.execute(
                    """
                    INSERT INTO idempotency_records (
                        record_id, tenant_id, idempotency_key, endpoint,
                        response_code, response_body, payload_hash, created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(tenant_id, endpoint, idempotency_key) DO UPDATE SET
                        response_code = excluded.response_code,
                        response_body = excluded.response_body,
                        payload_hash = excluded.payload_hash,
                        created_at = excluded.created_at,
                        expires_at = excluded.expires_at
                    """,
                    (
                        str(uuid4()), tenant_id, idempotency_key, endpoint, 200,
                        json.dumps(response, separators=(",", ":"), sort_keys=True),
                        payload_hash,
                        encode_timestamp(session, created_at),
                        encode_timestamp(session, expires_at),
                    ),
                )
            self.entries[key] = entry

    def acquire(
        self, key: tuple[str, str, str], payload_hash: str
    ) -> tuple[str, IdempotencyEntry | None]:
        """Atomically reserve a key or classify its existing record."""
        tenant_id, endpoint, idempotency_key = key
        with self._lock:
            for _ in range(2):
                now = time()
                lease_expires_at = now + self.lease_seconds
                with self.database.tenant_context(tenant_id) as session:
                    inserted = session.execute(
                        """
                        INSERT INTO idempotency_records (
                            record_id, tenant_id, idempotency_key, endpoint,
                            response_code, response_body, payload_hash, created_at, expires_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(tenant_id, endpoint, idempotency_key) DO NOTHING
                        RETURNING payload_hash
                        """,
                        (
                            str(uuid4()), tenant_id, idempotency_key, endpoint, 102, "{}",
                            payload_hash,
                            encode_timestamp(session, now),
                            encode_timestamp(session, lease_expires_at),
                        ),
                    )
                    if inserted:
                        self.entries.pop(key, None)
                        return "acquired", None
                    rows = session.execute(
                        """
                        SELECT payload_hash, response_body, response_code, expires_at
                        FROM idempotency_records
                        WHERE tenant_id = ? AND endpoint = ? AND idempotency_key = ?
                        """,
                        (tenant_id, endpoint, idempotency_key),
                    )
                    if not rows:
                        continue
                    row = rows[0]
                    expires_at = decode_timestamp(row["expires_at"])
                    if expires_at <= now:
                        session.execute(
                            """
                            DELETE FROM idempotency_records
                            WHERE tenant_id = ? AND endpoint = ? AND idempotency_key = ?
                            """,
                            (tenant_id, endpoint, idempotency_key),
                        )
                        continue
                    raw_response = row["response_body"]
                    entry = IdempotencyEntry(
                        payload_hash=str(row["payload_hash"]),
                        response=(
                            raw_response
                            if isinstance(raw_response, dict)
                            else json.loads(raw_response)
                        ),
                        expires_at=expires_at,
                        response_code=int(row["response_code"]),
                    )
                    if entry.payload_hash != payload_hash:
                        return "conflict", entry
                    if entry.response_code == 102:
                        return "in_progress", entry
                    self.entries[key] = entry
                    return "replay", entry
        raise RuntimeError("Unable to acquire idempotency reservation")

    def clear(self) -> None:
        with self._lock:
            self.entries.clear()
            if self.database.is_postgres:
                return
            with self.database.tenant_context("local-test") as session:
                session.execute("DELETE FROM idempotency_records")


def stable_payload_hash(payload: Any) -> str:
    normalized = payload.model_dump(mode="json", by_alias=True) if isinstance(payload, BaseModel) else payload
    canonical = json.dumps(
        normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


idempotency_store = IdempotencyStore()


def get_idempotent_response(
    *, action: str, payload: Any, ctx: RequestContext
) -> dict[str, Any] | None:
    payload_hash = stable_payload_hash(payload)
    outcome, entry = idempotency_store.acquire(
        (ctx.tenant_id, action, ctx.idempotency_key), payload_hash
    )
    if outcome == "acquired":
        return None
    if outcome == "conflict":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "idempotency_conflict",
                "message": "Idempotency-Key was already used with a different payload.",
            },
        )
    if outcome == "in_progress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "idempotency_in_progress",
                "message": "A request with this Idempotency-Key is still in progress.",
            },
        )
    assert entry is not None
    return entry.response


def store_idempotent_response(
    *, action: str, payload: Any, ctx: RequestContext, response: Any
) -> None:
    response_body = response.model_dump(mode="json") if isinstance(response, BaseModel) else dict(response)
    idempotency_store.put(
        (ctx.tenant_id, action, ctx.idempotency_key),
        payload_hash=stable_payload_hash(payload),
        response=response_body,
    )
