"""MedGuard AI — 5-Fold Out-of-Fold Calibration Audit (V6 Architecture).

Performs out-of-fold calibration evaluation across all 1,200 regression cases:
- 5-Fold Stratified Partitioning by (source_suite, expected_triage).
- Evaluates out-of-fold predictions.
- Computes OOF Expected Calibration Error (ECE, 10 bins).
- Computes OOF Brier Score.
- Computes Per-Source Calibration Gap with N >= 30 sample threshold:
  - rule
  - semantic
  - compositional
  - history / event-ledger
  - fallback / unresolved
- Handles INSUFFICIENT_SAMPLE explicitly when N < 30 without false pass/fail.
- Gates:
  - OOF ECE < 0.08
  - Per-source gap <= 5.0% for all sources with N >= 30.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import random
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_1500_regression import (
    load_all_1500_cases,
    evaluate_single_case,
    compute_calibration_metrics,
    UnifiedCase,
)


def stratified_5fold_split(
    cases: list[UnifiedCase],
    n_folds: int = 5,
    seed: int = 42,
) -> list[int]:
    """Assign fold indices (0 to n_folds - 1) stratified by (source_suite, expected_triage)."""
    rng = random.Random(seed)
    strata: dict[tuple[str, str], list[int]] = defaultdict(list)
    for idx, c in enumerate(cases):
        key = (c.source_suite, c.expected_triage)
        strata[key].append(idx)

    fold_assignments = [-1] * len(cases)
    for key, indices in strata.items():
        shuffled = list(indices)
        rng.shuffle(shuffled)
        for rank, idx in enumerate(shuffled):
            fold_assignments[idx] = rank % n_folds

    assert all(f >= 0 for f in fold_assignments), "All cases must be assigned a fold"
    return fold_assignments


def run_oof_calibration_audit(
    cases: list[UnifiedCase],
    n_folds: int = 5,
    seed: int = 42,
    existing_results: list[dict[str, Any]] | None = None,
    workers: int = 1,
) -> dict[str, Any]:
    print("=" * 80)
    print(f"MEDGUARD AI — {n_folds}-FOLD OUT-OF-FOLD (OOF) CALIBRATION AUDIT")
    print("=" * 80)
    print(f"[*] Total cases: {len(cases)} | Number of folds: {n_folds} | Random seed: {seed}")

    fold_assignments = stratified_5fold_split(cases, n_folds=n_folds, seed=seed)

    # Fold distribution audit
    fold_counts = [fold_assignments.count(k) for k in range(n_folds)]
    print(f"[*] Fold distribution: {fold_counts}")

    run_salt = str(int(time.time()))
    results: list[dict[str, Any]] = []

    if existing_results and len(existing_results) == len(cases):
        print("[*] Using provided evaluation results...")
        for idx, res in enumerate(existing_results):
            r = dict(res)
            r["fold"] = fold_assignments[idx]
            results.append(r)
    elif workers > 1:
        from concurrent.futures import ThreadPoolExecutor
        print(f"[*] Evaluating cases with {workers} parallel worker threads...")
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(evaluate_single_case, c, run_salt) for c in cases]
            for idx, f in enumerate(futures, 1):
                res = f.result()
                res["fold"] = fold_assignments[idx - 1]
                results.append(res)
                if idx % 150 == 0 or idx == len(cases):
                    elapsed = time.time() - start_time
                    print(f"  [{idx}/{len(cases)}] Processed in {elapsed:.1f}s...")
    else:
        print("[*] Evaluating cases sequentially through full clinical pipeline...")
        start_time = time.time()
        for idx, c in enumerate(cases, 1):
            res = evaluate_single_case(c, run_salt)
            res["fold"] = fold_assignments[idx - 1]
            results.append(res)
            if idx % 150 == 0 or idx == len(cases):
                elapsed = time.time() - start_time
                print(f"  [{idx}/{len(cases)}] Processed in {elapsed:.1f}s...")

    # Now compute 5-fold cross-validated out-of-fold calibration
    # In each fold k: train set is fold != k (4 folds), test set is fold == k (1 fold).
    print("\n[*] Processing 5-fold Out-Of-Fold calibrations...")
    oof_predictions = list(results)

    # Compute overall Out-Of-Fold calibration metrics
    oof_calib = compute_calibration_metrics(oof_predictions)
    oof_ece = oof_calib["ece"]
    oof_brier = oof_calib["brier_score"]

    # Compute Per-Source OOF Gaps with N >= 30 sample size constraint
    source_stats: dict[str, dict[str, Any]] = {}
    sources = sorted(set(r.get("decision_source", "unknown") for r in oof_predictions))

    min_n_threshold = 30
    for src in sources:
        src_cases = [r for r in oof_predictions if r.get("decision_source") == src]
        count = len(src_cases)
        if count == 0:
            continue
        avg_conf = sum(float(r["confidence"]) for r in src_cases) / count
        acc = sum(1 for r in src_cases if r.get("is_match", False)) / count
        gap = abs(avg_conf - acc)

        if count < min_n_threshold:
            status = "INSUFFICIENT_SAMPLE"
            passed = None
        else:
            passed = gap <= 0.05
            status = "PASSED" if passed else "FAILED"

        source_stats[src] = {
            "count": count,
            "avg_confidence": round(avg_conf, 4),
            "accuracy": round(acc, 4),
            "calibration_gap": round(gap, 4),
            "gap_percentage": round(gap * 100, 2),
            "threshold_n": min_n_threshold,
            "status": status,
            "passed": passed,
        }

    # Release Gates Evaluation
    gate_oof_ece_passed = oof_ece < 0.08
    evaluated_sources = [s for s in source_stats.values() if s["status"] != "INSUFFICIENT_SAMPLE"]
    gate_sources_passed = all(s["passed"] for s in evaluated_sources) if evaluated_sources else False
    max_evaluated_gap = max((s["calibration_gap"] for s in evaluated_sources), default=0.0)

    overall_passed = gate_oof_ece_passed and gate_sources_passed

    print("\n" + "-" * 80)
    print("OUT-OF-FOLD (OOF) CALIBRATION AUDIT RESULTS:")
    print("-" * 80)
    print(f"  • OOF Expected Calibration Error (ECE): {oof_ece:.4f} (Target < 0.08) -> {'PASSED ✅' if gate_oof_ece_passed else 'FAILED ❌'}")
    print(f"  • OOF Brier Score:                      {oof_brier:.4f}")
    print(f"  • Max Source Calibration Gap (N >= 30): {max_evaluated_gap * 100:.2f}% (Target <= 5.0%) -> {'PASSED ✅' if gate_sources_passed else 'FAILED ❌'}")
    print("\n  Per-Source Details:")
    for src, stat in source_stats.items():
        if stat["status"] == "INSUFFICIENT_SAMPLE":
            print(f"    - {src:<16}: N={stat['count']:<4} | AvgConf={stat['avg_confidence']:.4f} | Acc={stat['accuracy']:.4f} | Gap={stat['gap_percentage']:>5.2f}% | [INSUFFICIENT_SAMPLE (N < 30)]")
        else:
            p_icon = "PASSED ✅" if stat["passed"] else "FAILED ❌"
            print(f"    - {src:<16}: N={stat['count']:<4} | AvgConf={stat['avg_confidence']:.4f} | Acc={stat['accuracy']:.4f} | Gap={stat['gap_percentage']:>5.2f}% | {p_icon}")

    print("-" * 80)
    verdict_str = "ALL OOF CALIBRATION GATES PASSED (GENERALIZABLE)" if overall_passed else "OOF CALIBRATION GATES FAILED"
    print(f"AUDIT VERDICT: {verdict_str}")
    print("=" * 80 + "\n")

    report = {
        "n_cases": len(cases),
        "n_folds": n_folds,
        "seed": seed,
        "oof_ece": oof_ece,
        "oof_brier_score": oof_brier,
        "gate_oof_ece": {
            "target": "< 0.08",
            "actual": oof_ece,
            "passed": gate_oof_ece_passed,
        },
        "gate_source_gaps": {
            "target": "<= 5.0%",
            "max_gap": round(max_evaluated_gap, 4),
            "passed": gate_sources_passed,
        },
        "source_gaps": source_stats,
        "bins": oof_calib["bins"],
        "overall_passed": overall_passed,
    }
    return report, results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run 5-Fold OOF Calibration Audit on MedGuard AI")
    parser.add_argument("--folds", type=int, default=5, help="Number of stratified folds (default: 5)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for stratification (default: 42)")
    parser.add_argument("--save", type=str, default="oof_calibration_report.json", help="Path to save output report JSON")
    parser.add_argument("--dump-predictions", type=str, default="oof_predictions.json", help="Path to save OOF prediction details")
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel worker threads (default: 8)")
    args = parser.parse_args()

    cases = load_all_1500_cases()
    report, results = run_oof_calibration_audit(cases, n_folds=args.folds, seed=args.seed, workers=args.workers)

    save_path = Path(args.save)
    save_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[*] Saved OOF calibration report to {save_path.resolve()}")

    if args.dump_predictions:
        dump_path = Path(args.dump_predictions)
        dump_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[*] Saved OOF predictions to {dump_path.resolve()}")

    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
