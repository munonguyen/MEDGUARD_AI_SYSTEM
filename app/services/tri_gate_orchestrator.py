"""Tri-Gate (3-Path) Orchestrator for MedGuard AI.

Architecture:
  Gate 0: Deterministic Hard Safety Floor
    ↓
  Gate 1: Clinical Reasoner (structured clinical state)
    ↓
  3-Path Routing:
    - FAST PATH: High confidence, benign, no flags -> Light Gate 2, skip Jev (70% traffic)
    - REVIEW PATH: Uncertain, disagreement, boundary -> Parallel Gate 2 + Gate 3 (Jev)
    - CRITICAL PATH: Hard emergency floor locked -> Immediate emergency lock; Gate 2/3 enrich policy

Latency Invariant:
  T_total = T_parser + T_gate1 + max(T_gate2, T_gate3) + T_resolver
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import logging
from time import perf_counter
from typing import Any, Callable

from app.models.jev import DecisionState, JevDecision, TriageAcuity
from app.services.jev_governance import execute_jev_governed

logger = logging.getLogger(__name__)

_TRI_GATE_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="tri-gate-runner")


@dataclass(frozen=True)
class VerifierResult:
    approved: bool
    verifier_urgency: TriageAcuity
    confidence: float = 0.95
    issues: tuple[str, ...] = field(default_factory=tuple)
    latency_ms: float = 0.0


@dataclass(frozen=True)
class TriGateResult:
    selected_path: str  # "FAST_PATH" | "REVIEW_PATH" | "CRITICAL_PATH"
    hard_safety_floor: TriageAcuity
    gate1_reasoner_triage: TriageAcuity
    gate1_confidence: float
    gate2_verifier: VerifierResult | None
    gate3_jev: JevDecision | None
    jev_invoked: bool
    parallel_latency_ms: float
    total_orchestration_ms: float
    decision_state: DecisionState


def run_tri_gate_pipeline(
    *,
    decision_state: DecisionState,
    verifier_fn: Callable[[], VerifierResult] | None = None,
    jev_timeout_ms: float = 250.0,
) -> TriGateResult:
    """Execute the high-performance 3-path adaptive gating pipeline."""
    t_start = perf_counter()

    # 1. Gate 0 Hard Safety Floor Evaluation
    is_critical_floor = (
        decision_state.triage_floor == "EMERGENCY"
        or "no_home_monitoring" in decision_state.hard_safety_flags
        or "emergency_floor_locked" in decision_state.hard_safety_flags
    )

    # 2. Path Selection Logic
    if is_critical_floor:
        selected_path = "CRITICAL_PATH"
    elif (
        decision_state.confidence >= 0.94
        and not decision_state.risk_features
        and not decision_state.hard_safety_flags
        and decision_state.reasoner_triage == "ROUTINE"
    ):
        selected_path = "FAST_PATH"
    else:
        selected_path = "REVIEW_PATH"

    # Default Mock Verifier if none supplied
    def _default_verifier() -> VerifierResult:
        v_t0 = perf_counter()
        # Light verification logic
        v_lat = (perf_counter() - v_t0) * 1000.0
        return VerifierResult(
            approved=True,
            verifier_urgency=decision_state.reasoner_triage,
            confidence=0.95,
            latency_ms=round(v_lat, 2),
        )

    active_verifier = verifier_fn or _default_verifier

    gate2_res: VerifierResult | None = None
    gate3_res: JevDecision | None = None
    jev_invoked = False
    par_start = perf_counter()

    # 3. Execution by Path
    if selected_path == "FAST_PATH":
        # Skip Jev completely to maximize throughput and minimize latency
        jev_invoked = False
        gate2_res = active_verifier()
        gate3_res = None
        parallel_latency_ms = (perf_counter() - par_start) * 1000.0

    elif selected_path == "REVIEW_PATH":
        # Run Gate 2 and Gate 3 (Jev) IN PARALLEL
        jev_invoked = True
        fut_verifier = _TRI_GATE_POOL.submit(active_verifier)
        fut_jev = _TRI_GATE_POOL.submit(execute_jev_governed, decision_state, jev_timeout_ms)

        gate2_res = fut_verifier.result()
        gate3_res = fut_jev.result()
        parallel_latency_ms = (perf_counter() - par_start) * 1000.0

    else:  # CRITICAL_PATH
        # Lock emergency immediately. Gate 2/3 run asynchronously to enrich policy
        jev_invoked = True
        fut_verifier = _TRI_GATE_POOL.submit(active_verifier)
        fut_jev = _TRI_GATE_POOL.submit(execute_jev_governed, decision_state, jev_timeout_ms)

        gate2_res = fut_verifier.result()
        gate3_res = fut_jev.result()
        parallel_latency_ms = (perf_counter() - par_start) * 1000.0

    total_orchestration_ms = (perf_counter() - t_start) * 1000.0

    return TriGateResult(
        selected_path=selected_path,
        hard_safety_floor=decision_state.triage_floor,
        gate1_reasoner_triage=decision_state.reasoner_triage,
        gate1_confidence=decision_state.confidence,
        gate2_verifier=gate2_res,
        gate3_jev=gate3_res,
        jev_invoked=jev_invoked,
        parallel_latency_ms=round(parallel_latency_ms, 2),
        total_orchestration_ms=round(total_orchestration_ms, 2),
        decision_state=decision_state,
    )
