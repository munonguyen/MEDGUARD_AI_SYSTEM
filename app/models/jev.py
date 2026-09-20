"""Compact Typed Data Contracts for Gate 3 (Jev) Micro-Decision Engine.

Design Invariants:
1. Compact Decision State: Transmits ONLY essential triage hypotheses, risk features,
   hard safety flags, and candidate actions. NEVER transmits 20-turn chat histories,
   full medical textbooks, or heavy RAG context.
2. Abstract & PHI-Free: State hashes rely purely on clinical abstraction tokens,
   allowing safe, compliant in-memory caching.
3. Strict Typed Decisions: Output is a lean, unambiguous micro-decision structure
   designed for deterministic resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Literal

TriageAcuity = Literal["ROUTINE", "URGENT", "EMERGENCY"]
JevAction = Literal[
    "EMERGENCY_NOW",
    "SAME_DAY_EVAL",
    "SELF_CARE",
    "AMBIGUOUS_CLARIFY",
    "CALL_115",
]


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
        """Compute deterministic SHA-256 fingerprint of the clinical decision state.
        
        Purely captures abstraction tokens without patient PHI for safe caching.
        """
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
    """Typed micro-decision returned by Gate 3 (Jev)."""

    action: JevAction
    confidence: float
    allow_home_monitoring: bool
    require_human_review: bool
    triage_recommendation: TriageAcuity
    policy_rules_triggered: tuple[str, ...] = field(default_factory=tuple)
    latency_ms: float = 0.0
    source: str = "jev_engine"
    cached: bool = False
    circuit_breaker_bypassed: bool = False
    timeout_fallback: bool = False
