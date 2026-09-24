"""Jev (Gate 3) Causal Impact and Decision Attribution Engine for Blind V8.

Computes exact causal metrics comparing triage outcomes with and without Jev:
1. Jev Wrong -> Correct transitions (valuable corrections)
2. Jev Correct -> Wrong transitions (harmful overrides)
3. Jev Prevented Under-triage (safety interventions)
4. Jev Induced Under-triage (safety hazards)
5. Jev Prevented Over-triage (efficiency gains)
6. Jev Induced Over-triage (false alarms)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.tri_gate_resolver import _ACUITY_RANK


@dataclass(frozen=True)
class JevAttributionReport:
    total_cases: int
    jev_invoked_cases: int
    jev_invocation_rate_pct: float
    
    # Causal Transition Matrix
    wrong_to_correct: int
    correct_to_wrong: int
    net_accuracy_delta: int
    
    # Safety Impacts
    prevented_under_triage: int
    induced_under_triage: int
    net_under_triage_delta: int
    
    # Specificity / Over-triage Impacts
    prevented_over_triage: int
    induced_over_triage: int
    net_over_triage_delta: int
    
    # Detailed case IDs for auditing
    case_ids_prevented_under_triage: tuple[str, ...]
    case_ids_induced_under_triage: tuple[str, ...]
    case_ids_wrong_to_correct: tuple[str, ...]
    case_ids_correct_to_wrong: tuple[str, ...]


def evaluate_jev_causal_impact(
    predictions: list[dict[str, Any]],
    oracle_map: dict[str, dict[str, Any]],
) -> JevAttributionReport:
    total = len(predictions)
    invoked = 0
    
    wrong_to_correct = []
    correct_to_wrong = []
    
    prevented_under_triage = []
    induced_under_triage = []
    
    prevented_over_triage = []
    induced_over_triage = []

    for p in predictions:
        cid = p["case_id"]
        oracle = oracle_map.get(cid)
        if not oracle:
            continue
            
        oracle_triage = oracle["oracle_triage"]
        acceptable = oracle.get("acceptable_triage", [oracle_triage])
        
        without_jev = p.get("decision_without_jev", p["final_triage"])
        with_jev = p.get("decision_with_jev", p["final_triage"])
        jev_invoked = p.get("jev_invoked", False)
        
        if jev_invoked:
            invoked += 1
            
        is_without_ok = without_jev in acceptable
        is_with_ok = with_jev in acceptable
        
        # Accuracy transition
        if not is_without_ok and is_with_ok:
            wrong_to_correct.append(cid)
        elif is_without_ok and not is_with_ok:
            correct_to_wrong.append(cid)
            
        # Acuity comparisons
        rank_oracle = _ACUITY_RANK.get(oracle_triage, 1)
        rank_without = _ACUITY_RANK.get(without_jev, 1)
        rank_with = _ACUITY_RANK.get(with_jev, 1)
        
        # Under-triage analysis (when oracle is higher acuity)
        if rank_without < rank_oracle and rank_with >= rank_oracle:
            prevented_under_triage.append(cid)
        elif rank_without >= rank_oracle and rank_with < rank_oracle:
            induced_under_triage.append(cid)
            
        # Over-triage analysis (when oracle is lower acuity)
        if rank_without > rank_oracle and rank_with <= rank_oracle:
            prevented_over_triage.append(cid)
        elif rank_without <= rank_oracle and rank_with > rank_oracle:
            induced_over_triage.append(cid)

    rate = (invoked / total * 100.0) if total > 0 else 0.0

    return JevAttributionReport(
        total_cases=total,
        jev_invoked_cases=invoked,
        jev_invocation_rate_pct=round(rate, 2),
        wrong_to_correct=len(wrong_to_correct),
        correct_to_wrong=len(correct_to_wrong),
        net_accuracy_delta=len(wrong_to_correct) - len(correct_to_wrong),
        prevented_under_triage=len(prevented_under_triage),
        induced_under_triage=len(induced_under_triage),
        net_under_triage_delta=len(prevented_under_triage) - len(induced_under_triage),
        prevented_over_triage=len(prevented_over_triage),
        induced_over_triage=len(induced_over_triage),
        net_over_triage_delta=len(prevented_over_triage) - len(induced_over_triage),
        case_ids_prevented_under_triage=tuple(prevented_under_triage),
        case_ids_induced_under_triage=tuple(induced_under_triage),
        case_ids_wrong_to_correct=tuple(wrong_to_correct),
        case_ids_correct_to_wrong=tuple(correct_to_wrong),
    )
