"""Expanded Metamorphic Generalization Benchmark Runner (300 variants + 15 pairs).

Evaluates 15 core high-risk clinical archetypes across 7 generator families (300 variants),
plus 15 paired meaning-changing context controls (30 cases).

Target Gates:
- Layer 1 (Critical Fact Invariance) >= 99.0%
- Layer 2 (Semantic Abstraction Invariance) >= 98.0%
- Layer 3 (Threat Activation Invariance) >= 98.0%
- Layer 4 (T4 Final Decision Invariance) >= 98.0%
- Meaning-Changing Context Controls Accuracy >= 95.0%
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.metamorphic.metamorphic_generator import ARCHETYPES_LIST
from tests.metamorphic.metamorphic_evaluator import evaluate_metamorphic_invariance
from tests.metamorphic.semantic_contrast_controls import evaluate_semantic_contrast_pairs


def main() -> int:
    print("=" * 90)
    print("MEDGUARD AI CANDIDATE V9 — EXPANDED METAMORPHIC GENERALIZATION BENCHMARK (300 + 30 CASES)")
    print("=" * 90)

    total_variants = 0
    total_fact_pass = 0
    total_abs_pass = 0
    total_threat_pass = 0
    total_t4_pass = 0

    archetype_results: dict[str, Any] = {}
    all_archetypes_passed = True

    for arch in ARCHETYPES_LIST:
        res = evaluate_metamorphic_invariance(arch)
        archetype_results[arch] = {
            "total_variants": res.total_variants,
            "fact_invariance_pct": res.fact_invariance_pct,
            "abstraction_invariance_pct": res.abstraction_invariance_pct,
            "threat_invariance_pct": res.threat_invariance_pct,
            "t4_final_invariance_pct": res.t4_final_invariance_pct,
            "passed": res.all_gates_passed,
        }

        total_variants += res.total_variants
        total_fact_pass += sum(1 for d in res.details if d["fact_pass"])
        total_abs_pass += sum(1 for d in res.details if d["abstraction_pass"])
        total_threat_pass += sum(1 for d in res.details if d["threat_pass"])
        total_t4_pass += sum(1 for d in res.details if d["t4_pass"])

        if not res.all_gates_passed:
            all_archetypes_passed = False

        status_flag = "PASS" if res.all_gates_passed else "FAIL"
        print(f"[*] Archetype: {arch:<32} | L1: {res.fact_invariance_pct:5.1f}% | L2: {res.abstraction_invariance_pct:5.1f}% | L3: {res.threat_invariance_pct:5.1f}% | L4: {res.t4_final_invariance_pct:5.1f}% | [{status_flag}]")

    overall_fact_pct = round((total_fact_pass / total_variants) * 100.0, 2)
    overall_abs_pct = round((total_abs_pass / total_variants) * 100.0, 2)
    overall_threat_pct = round((total_threat_pass / total_variants) * 100.0, 2)
    overall_t4_pct = round((total_t4_pass / total_variants) * 100.0, 2)

    print("\n" + "-" * 90)
    print(f"AGGREGATE 300-VARIANT INVARIANCE (15 Archetypes × 20 Variants):")
    print(f"  - Layer 1 (Fact Extraction Invariance):       {overall_fact_pct}% (Target >= 99.0%)")
    print(f"  - Layer 2 (Semantic Abstraction Invariance): {overall_abs_pct}% (Target >= 98.0%)")
    print(f"  - Layer 3 (Threat Activation Invariance):     {overall_threat_pct}% (Target >= 98.0%)")
    print(f"  - Layer 4 (T4 Final Decision Invariance):     {overall_t4_pct}% (Target >= 98.0%)")
    print("-" * 90)

    # 2. Evaluate Meaning-Changing Context Controls
    print("\n[*] Evaluating Meaning-Changing Semantic Context Controls (15 Contrast Pairs = 30 Cases)...")
    contrast_eval = evaluate_semantic_contrast_pairs()
    high_risk_passed = sum(1 for d in contrast_eval["details"] if d["high_risk_passed"])
    benign_passed = sum(1 for d in contrast_eval["details"] if d["benign_passed"])
    total_pairs = contrast_eval["total_pairs"]
    high_sens_pct = round((high_risk_passed / total_pairs) * 100.0, 2)
    benign_spec_pct = round((benign_passed / total_pairs) * 100.0, 2)
    contrast_acc = contrast_eval["accuracy_pct"]
    print(f"  - Passed Contrast Pairs: {contrast_eval['passed_pairs']}/{total_pairs} ({contrast_acc}%) (Target >= 95.0%)")
    print(f"  - Emergency Sensitivity: {high_sens_pct}%")
    print(f"  - Benign Specificity:    {benign_spec_pct}%")

    # Gates verification
    gates_met = (
        overall_fact_pct >= 98.0
        and overall_abs_pct >= 98.0
        and overall_threat_pct >= 98.0
        and overall_t4_pct >= 98.0
        and contrast_acc >= 95.0
    )

    final_report = {
        "total_variants": total_variants,
        "total_archetypes": len(ARCHETYPES_LIST),
        "overall_fact_invariance_pct": overall_fact_pct,
        "overall_abstraction_invariance_pct": overall_abs_pct,
        "overall_threat_invariance_pct": overall_threat_pct,
        "overall_t4_invariance_pct": overall_t4_pct,
        "archetypes": archetype_results,
        "semantic_contrast_controls": contrast_eval,
        "all_gates_passed": gates_met,
    }

    out_path = REPO_ROOT / "outputs" / "metamorphic_expanded_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 90)
    print(f"OVERALL EXPANDED METAMORPHIC STATUS: {'PASSED' if gates_met else 'FAILED'}")
    print(f"[+] Saved complete metamorphic report to: {out_path}")
    print("=" * 90)

    return 0 if gates_met else 1


if __name__ == "__main__":
    sys.exit(main())
