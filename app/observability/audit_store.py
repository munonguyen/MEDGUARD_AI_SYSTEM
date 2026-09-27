"""Immutable In-Process Clinical Decision Audit Store.

Stores and indexes clinical traces to support retrospective inquiry, medical compliance audits,
and post-market surveillance (e.g. "Reconstruct why the system escalated patient X on 26/09/2026").
"""

from __future__ import annotations

from typing import Any
from app.observability.tracing import ClinicalTrace


class AuditStore:
    """In-process append-only store for ClinicalTrace records."""

    def __init__(self, max_capacity: int = 10000) -> None:
        self.max_capacity = max_capacity
        self._traces: dict[str, ClinicalTrace] = {}
        self._order: list[str] = []

    def record_trace(self, trace: ClinicalTrace) -> None:
        """Appends a trace immutably into the store."""
        if len(self._order) >= self.max_capacity:
            oldest = self._order.pop(0)
            self._traces.pop(oldest, None)

        self._traces[trace.trace_id] = trace
        self._order.append(trace.trace_id)

    def get_trace(self, trace_id: str) -> ClinicalTrace | None:
        """Retrieves a single trace by ID."""
        return self._traces.get(trace_id)

    def query(
        self,
        urgency: str | None = None,
        arbitration_action: str | None = None,
        limit: int = 50,
    ) -> list[ClinicalTrace]:
        """Queries historical traces by clinical filters."""
        results: list[ClinicalTrace] = []
        for tid in reversed(self._order):
            trace = self._traces[tid]
            if urgency and trace.final_urgency != urgency:
                continue
            if arbitration_action and trace.arbitration_action != arbitration_action:
                continue
            results.append(trace)
            if len(results) >= limit:
                break
        return results


# Global default instance
default_audit_store = AuditStore()
