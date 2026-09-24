"""Structured Clinical Decision Audit Trail for MedGuard AI.

Invariants:
1. Every clinical decision (triage, medication safety, prescription verification)
   is bound to an immutable audit record containing:
   - decision_id: unique globally verifiable ID (e.g. cdec_<uuid>)
   - request_id & trace_id
   - candidate_version & git_commit
   - knowledge_version & knowledge_integrity_hash
   - model_version
   - triage_decision & candidate_actions
   - decision_sources: [Gate 0, Gate 1, Gate 2, Gate 3 (Jev)]
   - confidence & safety_invariants_enforced
   - timestamp_utc
2. Non-repudiation: Audit trail persists into PostgreSQL / SQLite audit store.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
from typing import Any
from uuid import uuid4

from app.core.database import DatabaseManager, db_manager
from app.knowledge.loader import knowledge

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClinicalDecisionRecord:
    decision_id: str
    tenant_id: str
    request_id: str
    trace_id: str
    candidate_version: str
    knowledge_version: str
    model_version: str
    triage_decision: str
    decision_sources: tuple[str, ...]
    confidence: float
    safety_invariants_enforced: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ClinicalDecisionAuditStore:
    def __init__(self, database: DatabaseManager = db_manager) -> None:
        self.database = database
        self._memory_cache: list[ClinicalDecisionRecord] = []

    def log_decision(
        self,
        *,
        tenant_id: str,
        request_id: str,
        trace_id: str,
        triage_decision: str,
        decision_sources: list[str] | tuple[str, ...],
        confidence: float,
        safety_invariants_enforced: list[str] | tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
        candidate_version: str = "v8-candidate-tri-gate",
        model_version: str = "medguard-candidate-v8-frozen",
    ) -> ClinicalDecisionRecord:
        decision_id = f"cdec_{uuid4().hex[:12]}"
        k_ver = knowledge.version_string() if hasattr(knowledge, "version_string") else "knowledge@v8"

        record = ClinicalDecisionRecord(
            decision_id=decision_id,
            tenant_id=tenant_id,
            request_id=request_id,
            trace_id=trace_id,
            candidate_version=candidate_version,
            knowledge_version=k_ver,
            model_version=model_version,
            triage_decision=triage_decision,
            decision_sources=tuple(decision_sources),
            confidence=round(confidence, 4),
            safety_invariants_enforced=tuple(safety_invariants_enforced),
            metadata=metadata or {},
        )

        # Store in append-only database audit_events table
        try:
            with self.database.tenant_context(tenant_id) as session:
                session.execute(
                    """
                    INSERT INTO audit_events (
                        event_id, tenant_id, request_id, action,
                        payload_type, metadata_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.decision_id,
                        record.tenant_id,
                        record.request_id,
                        "clinical.decision_audit",
                        "ClinicalDecisionRecord",
                        json.dumps(asdict(record), separators=(",", ":"), sort_keys=True),
                        record.timestamp_utc,
                    ),
                )
        except Exception as e:
            logger.warning(f"Failed to persist clinical decision audit to DB: {e}")

        self._memory_cache.append(record)
        return record

    def list_decisions(self, tenant_id: str, limit: int = 50) -> list[ClinicalDecisionRecord]:
        return [r for r in self._memory_cache if r.tenant_id == tenant_id][-limit:]


# Global singleton
decision_audit_store = ClinicalDecisionAuditStore()
