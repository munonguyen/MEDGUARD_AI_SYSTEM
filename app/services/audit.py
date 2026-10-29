"""Append-only, tenant-scoped audit event repository."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any
from uuid import uuid4

from app.core.database import DatabaseManager, db_manager
from app.core.repository import AuditEventRepository


@dataclass
class AuditEvent:
    request_id: str
    tenant_id: str
    action: str
    payload_type: str
    metadata: dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AuditStore:
    def __init__(
        self,
        database: DatabaseManager = db_manager,
        repository: AuditEventRepository | None = None,
    ) -> None:
        self.database = database
        self.repository = repository or AuditEventRepository(database=database)
        self._lock = RLock()
        self.events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        with self._lock:
            self.repository.record_event(
                tenant_id=event.tenant_id,
                event_id=str(uuid4()),
                request_id=event.request_id,
                action=event.action,
                payload_type=event.payload_type,
                metadata_json=json.dumps(event.metadata, separators=(",", ":"), sort_keys=True),
                created_at=event.created_at,
            )
            self.events.append(event)

    def query(self, tenant_id: str, request_id: str | None = None) -> list[AuditEvent]:
        with self._lock:
            rows = self.repository.query_events(tenant_id, request_id)
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
            self.repository.clear()


audit_store = AuditStore()
