"""Enlarged 3-Tier Benchmark for MedGuard AI Candidate V9 (120 Cases).

Evaluates the clinical pipeline across three decoupled validation tiers:
- Tier A: Semantic Representation Benchmark (Text -> Clinical Facts & Physiologic Archetypes)
- Tier B: Routing Benchmark (Representation -> Clinical Threat / Toxicology / Singleton Routing)
- Tier C: End-to-End Triage Benchmark (Full Tri-Gate Acuity Resolution)

Includes:
- 60 True Emergency Presentations across 15 clinical syndromes
- 60 Benign / Physiologic Negative Controls across matching domains

Target Gates:
- Tier A Representation Recall >= 99.0%, Precision >= 95.0%
- Tier B Routing Recall >= 99.0%, Routing Precision >= 95.0%
- Tier C Pure T4 Sensitivity >= 99.0%, Specificity >= 95.0%
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.semantic_relation_extractor import extract_semantic_relations
from app.services.semantic_abstraction_lattice import evaluate_abstraction_lattice, AbstractThreatArchetype
from app.services.toxicology_signature_router import route_by_toxicity_signature
from app.services.evidence_strength_scorer import score_evidence_strength, SingletonEvidenceTier
from app.services.rules import triage_rules
from tests.benchmarks.benchmark_toxicology_v9 import generate_toxicology_test_suite
from tests.benchmarks.benchmark_singleton_v9 import generate_singleton_test_suite
from tests.metamorphic.semantic_contrast_controls import SEMANTIC_CONTRAST_PAIRS


@dataclass(frozen=True)
class TierCase:
    case_id: str
    text: str
    is_emergency: bool
    expected_domain: str
    description: str


def build_120_tier_dataset() -> list[TierCase]:
    cases: list[TierCase] = []

    # 1. Add 15 Emergency + 15 Benign from Semantic Contrast Controls (30 cases)
    for p in SEMANTIC_CONTRAST_PAIRS:
        cases.append(TierCase(
            case_id=f"{p.pair_id}-EM",
            text=p.high_risk_text,
            is_emergency=True,
            expected_domain=p.domain,
            description=p.differentiation_basis,
        ))
        cases.append(TierCase(
            case_id=f"{p.pair_id}-NORM",
            text=p.benign_text,
            is_emergency=False,
            expected_domain=p.domain,
            description=p.differentiation_basis,
        ))

    # 2. Add 25 Emergency + 25 Benign from Toxicology Benchmark (50 cases)
    tox_cases = generate_toxicology_test_suite()
    tox_pos = [c for c in tox_cases if c.is_toxic][:25]
    tox_neg = [c for c in tox_cases if not c.is_toxic][:25]
    for c in tox_pos:
        cases.append(TierCase(
            case_id=c.case_id,
            text=c.text,
            is_emergency=True,
            expected_domain="toxicology",
            description=c.description,
        ))
    for c in tox_neg:
        cases.append(TierCase(
            case_id=c.case_id,
            text=c.text,
            is_emergency=False,
            expected_domain="benign_exposure",
            description=c.description,
        ))

    # 3. Add 20 Emergency + 20 Benign from Critical Singleton Benchmark (40 cases)
    sgt_cases = generate_singleton_test_suite()
    sgt_pos = [c for c in sgt_cases if c.is_critical_singleton][:20]
    sgt_neg = [c for c in sgt_cases if not c.is_critical_singleton][:20]
    for c in sgt_pos:
        cases.append(TierCase(
            case_id=c.case_id,
            text=c.text,
            is_emergency=True,
            expected_domain="singleton_emergency",
            description=c.description,
        ))
    for c in sgt_neg:
        cases.append(TierCase(
            case_id=c.case_id,
            text=c.text,
            is_emergency=False,
            expected_domain="benign_singleton",
            description=c.description,
        ))

    return cases


def run_enlarged_tiered_benchmark() -> dict[str, Any]:
    print("=" * 85)
    print("MEDGUARD AI CANDIDATE V9 — ENLARGED 3-TIER BENCHMARK (120 CASES)")
    print("=" * 85)

    cases = build_120_tier_dataset()
    total = len(cases)
    em_cases = [c for c in cases if c.is_emergency]
    benign_cases = [c for c in cases if not c.is_emergency]

    print(f"[*] Total Test Cases: {total} (Emergency: {len(em_cases)}, Benign Controls: {len(benign_cases)})")

    # -------------------------------------------------------------------------
    # Tier A: Representation Benchmark
    # -------------------------------------------------------------------------
    tier_a_tp = 0
    tier_a_fn = 0
    tier_a_tn = 0
    tier_a_fp = 0

    # -------------------------------------------------------------------------
    # Tier B: Routing Benchmark
    # -------------------------------------------------------------------------
    tier_b_tp = 0
    tier_b_fn = 0
    tier_b_tn = 0
    tier_b_fp = 0

    # -------------------------------------------------------------------------
    # Tier C: End-to-End Triage Benchmark
    # -------------------------------------------------------------------------
    tier_c_tp = 0
    tier_c_fn = 0
    tier_c_tn = 0
    tier_c_fp = 0

    for c in cases:
        txt = c.text

        # 1. Evaluate Representation (Extract facts and higher-order abstractions across all 3 mechanisms)
        graph = extract_semantic_relations(txt)
        lattice_res = evaluate_abstraction_lattice(graph)
        tox_res = route_by_toxicity_signature(txt)
        sgt_res = score_evidence_strength(txt)

        has_extracted_facts = len(graph.concepts) >= 1 or len(tox_res.matched_dimensions) >= 1 or sgt_res.tier != SingletonEvidenceTier.WEAK_SINGLETON
        has_emergency_abstraction = (
            lattice_res.has_emergency_threat
            or tox_res.is_emergency_toxidrome
            or (sgt_res.tier == SingletonEvidenceTier.CRITICAL_SINGLETON)
        )

        if c.is_emergency:
            if has_extracted_facts and has_emergency_abstraction:
                tier_a_tp += 1
            else:
                tier_a_fn += 1
        else:
            if not has_emergency_abstraction or lattice_res.has_benign_override:
                tier_a_tn += 1
            else:
                tier_a_fp += 1

        # 2. Evaluate Routing (Route to appropriate clinical pathway)
        is_routed_emergency = has_emergency_abstraction

        if c.is_emergency:
            if is_routed_emergency:
                tier_b_tp += 1
            else:
                tier_b_fn += 1
        else:
            if not is_routed_emergency:
                tier_b_tn += 1
            else:
                tier_b_fp += 1

        # 3. Evaluate End-to-End Triage (Final Tri-Gate Acuity)
        rule_res = triage_rules(txt)
        is_triage_emergency = rule_res.urgency == "EMERGENCY"

        if c.is_emergency:
            if is_triage_emergency:
                tier_c_tp += 1
            else:
                tier_c_fn += 1
        else:
            if not is_triage_emergency:
                tier_c_tn += 1
            else:
                tier_c_fp += 1

    # Metrics
    tier_a_recall = (tier_a_tp / len(em_cases) * 100.0) if em_cases else 0.0
    tier_a_precision = (tier_a_tp / (tier_a_tp + tier_a_fp) * 100.0) if (tier_a_tp + tier_a_fp) else 0.0

    tier_b_recall = (tier_b_tp / len(em_cases) * 100.0) if em_cases else 0.0
    tier_b_precision = (tier_b_tp / (tier_b_tp + tier_b_fp) * 100.0) if (tier_b_tp + tier_b_fp) else 0.0

    tier_c_sens = (tier_c_tp / len(em_cases) * 100.0) if em_cases else 0.0
    tier_c_spec = (tier_c_tn / len(benign_cases) * 100.0) if benign_cases else 0.0

    print("\n" + "-" * 85)
    print(f"TIER A (Representation): Recall = {tier_a_recall:.2f}% (TP={tier_a_tp}/{len(em_cases)}, FN={tier_a_fn}) | Precision = {tier_a_precision:.2f}% (TN={tier_a_tn}/{len(benign_cases)}, FP={tier_a_fp})")
    print(f"TIER B (Routing):        Recall = {tier_b_recall:.2f}% (TP={tier_b_tp}/{len(em_cases)}, FN={tier_b_fn}) | Precision = {tier_b_precision:.2f}% (TN={tier_b_tn}/{len(benign_cases)}, FP={tier_b_fp})")
    print(f"TIER C (End-to-End):     Sensitivity = {tier_c_sens:.2f}% (TP={tier_c_tp}/{len(em_cases)}, FN={tier_c_fn}) | Specificity = {tier_c_spec:.2f}% (TN={tier_c_tn}/{len(benign_cases)}, FP={tier_c_fp})")
    print("-" * 85)

    all_passed = (
        tier_a_recall >= 99.0 and tier_a_precision >= 95.0 and
        tier_b_recall >= 99.0 and tier_b_precision >= 95.0 and
        tier_c_sens >= 99.0 and tier_c_spec >= 95.0
    )
    print(f"OVERALL 3-TIER VALIDATION STATUS: {'PASSED' if all_passed else 'FAILED'}")
    print("=" * 85)

    report = {
        "total_cases": total,
        "emergency_cases": len(em_cases),
        "benign_cases": len(benign_cases),
        "tier_a": {
            "recall_pct": round(tier_a_recall, 2),
            "precision_pct": round(tier_a_precision, 2),
            "tp": tier_a_tp, "fn": tier_a_fn, "tn": tier_a_tn, "fp": tier_a_fp,
            "passed": tier_a_recall >= 99.0 and tier_a_precision >= 95.0,
        },
        "tier_b": {
            "recall_pct": round(tier_b_recall, 2),
            "precision_pct": round(tier_b_precision, 2),
            "tp": tier_b_tp, "fn": tier_b_fn, "tn": tier_b_tn, "fp": tier_b_fp,
            "passed": tier_b_recall >= 99.0 and tier_b_precision >= 95.0,
        },
        "tier_c": {
            "sensitivity_pct": round(tier_c_sens, 2),
            "specificity_pct": round(tier_c_spec, 2),
            "tp": tier_c_tp, "fn": tier_c_fn, "tn": tier_c_tn, "fp": tier_c_fp,
            "passed": tier_c_sens >= 99.0 and tier_c_spec >= 95.0,
        },
        "overall_passed": all_passed,
    }

    out_file = REPO_ROOT / "outputs" / "tiered_benchmark_100plus_report.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"[+] Saved enlarged tiered report to: {out_file}")
    return report


if __name__ == "__main__":
    run_enlarged_tiered_benchmark()
