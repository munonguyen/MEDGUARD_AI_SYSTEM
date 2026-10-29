"""Compact Typed Data Contracts for Gate 3 (Jev) Micro-Decision Engine.

V14 authority model:
1. Jev is a compact clinical-safety knowledge anchor and advisory arbiter.
2. Jev may surface risk, insights and clarification needs, but it is not a
   standalone non-emergency disposition authority.
3. Only an explicit emergency lock may act as fail-closed authority. Normal
   ROUTINE/URGENT resolution belongs to the upstream reasoner/verifier resolver.
4. State remains abstract and PHI-free so cache keys never require raw patient
   identifiers or long conversation histories.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Literal

TriageAcuity = Literal["ROUTINE", "URGENT", "EMERGENCY"]
JevAction = Literal[
    "EMERGENCY_NOW",
    "SAME_DAY_EVAL",
    "SELF_CARE",
    "AMBIGUOUS_CLARIFY",
    "CALL_115",
]
JevAuthority = Literal["advisory", "emergency_lock"]


@dataclass(frozen=True)
class DecisionState:
    """Minimal typed decision state passed to Gate 3 (Jev)."""

    triage_floor: TriageAcuity
    reasoner_triage: TriageAcuity
    verifier_pending: bool = True
    risk_features: tuple[str, ...] = field(default_factory=tuple)
    hard_safety_flags: tuple[str, ...] = field(default_factory=tuple)
    candidate_actions: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.95
    fact_coverage: float = 1.0
    symptoms_summary: str = ""

    def state_hash(self) -> str:
        """Compute a deterministic PHI-free fingerprint of the decision state."""
        raw_payload = {
            "floor": self.triage_floor,
            "reasoner": self.reasoner_triage,
            "features": sorted(self.risk_features),
            "flags": sorted(self.hard_safety_flags),
            "actions": sorted(self.candidate_actions),
            "coverage_bin": round(self.fact_coverage, 1),
        }
        encoded = json.dumps(raw_payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]


@dataclass(frozen=True)
class JevDecision:
    """Typed advisory micro-decision returned by Gate 3 (Jev).

    ``authority`` defaults to ``advisory``. Existing Jev rule output therefore
    cannot silently become a ROUTINE->URGENT/EMERGENCY override. A future rule
    may set ``emergency_lock`` only when it represents an explicit fail-closed
    emergency invariant rather than a probabilistic preference.
    """

    action: JevAction
    confidence: float
    allow_home_monitoring: bool
    require_human_review: bool
    triage_recommendation: TriageAcuity
    policy_rules_triggered: tuple[str, ...] = field(default_factory=tuple)
    clinical_insights: tuple[str, ...] = field(default_factory=tuple)
    advisory_red_flags: tuple[str, ...] = field(default_factory=tuple)
    suggested_clarifications: tuple[str, ...] = field(default_factory=tuple)
    authority: JevAuthority = "advisory"
    latency_ms: float = 0.0
    source: str = "jev_engine"
    cached: bool = False
    circuit_breaker_bypassed: bool = False
    timeout_fallback: bool = False
