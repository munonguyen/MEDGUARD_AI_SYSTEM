"""Append-only, tenant-scoped audit event repository."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any
from uuid import uuid4

from app.core.database import DatabaseManager, db_manager


@dataclass
class AuditEvent:
    request_id: str
    tenant_id: str
    action: str
    payload_type: str
    metadata: dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AuditStore:
    def __init__(self, database: DatabaseManager = db_manager) -> None:
        self.database = database
        self._lock = RLock()
        self.events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        with self._lock:
            with self.database.tenant_context(event.tenant_id) as session:
                session.execute(
                    """
                    INSERT INTO audit_events (
                        event_id, tenant_id, request_id, action,
                        payload_type, metadata_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()), event.tenant_id, event.request_id, event.action,
                        event.payload_type,
                        json.dumps(event.metadata, separators=(",", ":"), sort_keys=True),
                        event.created_at,
                    ),
                )
            self.events.append(event)

    def query(self, tenant_id: str, request_id: str | None = None) -> list[AuditEvent]:
        query = """
            SELECT request_id, tenant_id, action, payload_type, metadata_json, created_at
            FROM audit_events
            WHERE tenant_id = ?
        """
        params: tuple[str, ...] = (tenant_id,)
        if request_id:
            query += " AND request_id = ?"
            params += (request_id,)
        query += " ORDER BY created_at ASC"
        with self._lock:
            with self.database.tenant_context(tenant_id) as session:
                rows = session.execute(query, params)
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: dict[str, Any]) -> AuditEvent:
        raw_metadata = row["metadata_json"]
        metadata = raw_metadata if isinstance(raw_metadata, dict) else json.loads(raw_metadata)
        raw_created_at = row["created_at"]
        created_at = (
            raw_created_at.astimezone(timezone.utc).isoformat()
            if isinstance(raw_created_at, datetime)
            else str(raw_created_at)
        )
        return AuditEvent(
            request_id=str(row["request_id"]),
            tenant_id=str(row["tenant_id"]),
            action=str(row["action"]),
            payload_type=str(row["payload_type"]),
            metadata=metadata,
            created_at=created_at,
        )

    def clear(self) -> None:
        with self._lock:
            self.events.clear()
            if self.database.is_postgres:
                return
            with self.database.tenant_context("local-test") as session:
                session.execute("DELETE FROM audit_events")


audit_store = AuditStore()
