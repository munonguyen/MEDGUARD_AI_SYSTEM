"""Clinical Decision Tracing and Telemetry.

Captures the comprehensive end-to-end execution path for every clinical request,
including Canonical State Hash, KB Snapshot ID, Retrieval Plan, Claim Ledger lifecycle,
Jev Micro-Scores, and Stage Latencies.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


class ClinicalTrace(BaseModel):
    """Immutable execution trace of a single clinical consultation."""
    trace_id: str = Field(default_factory=lambda: f"TRC_{uuid.uuid4().hex[:12]}")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    intake_version: str = "v3.0"
    ccs_hash: str = Field(description="SHA-256 hash of the Canonical Clinical State")
    kb_snapshot_id: str = Field(description="Frozen KB snapshot tag used for this execution")
    retrieval_plan: dict[str, Any] = Field(default_factory=dict)
    retrieved_evidence_ids: list[str] = Field(default_factory=list)
    claim_lifecycle: list[dict[str, Any]] = Field(default_factory=list)
    critic_violations: list[dict[str, Any]] = Field(default_factory=list)
    jev_judgment: dict[str, Any] = Field(default_factory=dict)
    arbitration_action: str = "ACCEPT_A"
    output_guard_safe: bool = True
    final_urgency: str = "ROUTINE"
    latencies_ms: dict[str, float] = Field(default_factory=dict)
