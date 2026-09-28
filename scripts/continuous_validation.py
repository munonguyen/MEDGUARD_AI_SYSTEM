"""Repeat regression and data quality gates to detect instability across runs."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.services.readiness import build_readiness
from scripts.benchmark_adversarial import run_adversarial_benchmark
from scripts.benchmark_chat_hard import run_chat_hard_benchmark
from scripts.benchmark_mimic_ed import run_mimic_ed_benchmark
from scripts.benchmark_llm_control_plane import run_llm_control_plane_benchmark
from scripts.benchmark_ocr import run_ocr_benchmark
from scripts.benchmark_professional_response import run_professional_response_benchmark
from scripts.benchmark_runtime import run_runtime_benchmark
from scripts.benchmark_safety import run_allergy_benchmark, run_interaction_benchmark
from scripts.benchmark_triage import run_triage_benchmark
from scripts.validate_external_datasets import validate_mimic_demo
from scripts.validate_training_plane import validate_training_plane


def _run_iteration(iteration: int, profile: str) -> bool:
    test_run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    ocr = run_ocr_benchmark()
    triage = run_triage_benchmark()
    interactions = run_interaction_benchmark()
    allergies = run_allergy_benchmark()
    adversarial = run_adversarial_benchmark()
    chat_hard = run_chat_hard_benchmark()
    output_quality = run_professional_response_benchmark()
    external_integrity = validate_mimic_demo()
    mimic = run_mimic_ed_benchmark()
    runtime = run_runtime_benchmark(iterations_per_endpoint=25)
    llm_control = run_llm_control_plane_benchmark(iterations=500, workers=10)
    readiness = build_readiness()
    training_plane = validate_training_plane()

    common_gate = all(
        (
            test_run.returncode == 0,
            triage["kappa_passed"],
            triage["undertriage_passed"],
            triage["emergency_recall_passed"],
            interactions["recall_passed"],
            interactions["precision_passed"],
            allergies["recall_passed"],
            adversarial["fail_closed_passed"],
            adversarial["zero_default_catalog_violations"],
            chat_hard["gate_passed"],
            output_quality["gate_passed"],
            external_integrity["valid"],
            runtime["development_gate_passed"],
            llm_control["all_passed"],
            training_plane["all_passed"],
        )
    )
    production_gate = all(
        (
            common_gate,
            readiness.production_ready,
            ocr["ocr_status"] == "evaluated",
            ocr["cer_passed"],
            ocr["wer_passed"],
            ocr["precision_passed"],
            mimic["production_evaluable"],
            mimic["emergency_recall"] >= 0.98,
            mimic["severe_undertriage_rate"] <= 0.01,
            output_quality["critical_failures"] == [],
            output_quality["false_accepts"] == [],
        )
    )
    passed = production_gate if profile == "production" else common_gate
    test_summary = test_run.stdout.strip().splitlines()[-1] if test_run.stdout.strip() else "pytest failed"
    print(
        f"iteration={iteration} profile={profile} gate={'PASS' if passed else 'FAIL'} "
        f"tests=({test_summary}) ocr={ocr['ocr_status']} "
        f"external_integrity={'valid' if external_integrity['valid'] else 'invalid'} "
        f"external_emergency_recall={mimic['emergency_recall']} "
        f"runtime_p95_ms={runtime['max_endpoint_p95_ms']} "
        f"llm_control={'pass' if llm_control['all_passed'] else 'fail'} "
        f"chat_hard={chat_hard['passed']}/{chat_hard['total']} "
        f"output_quality={output_quality['correct']}/{output_quality['total']} "
        f"quality_score={output_quality['average_good_score']} "
        f"training_plane={'pass' if training_plane['all_passed'] else 'fail'} "
        f"readiness={readiness.status} production_ready={readiness.production_ready}"
    )
    return passed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--interval-seconds", type=float, default=0.0)
    parser.add_argument("--profile", choices=("development", "production"), default="development")
    args = parser.parse_args()
    if args.iterations < 1 or args.interval_seconds < 0:
        parser.error("iterations must be >= 1 and interval-seconds must be >= 0")

    results = []
    for iteration in range(1, args.iterations + 1):
        results.append(_run_iteration(iteration, args.profile))
        if iteration < args.iterations and args.interval_seconds:
            time.sleep(args.interval_seconds)
    stable = all(results) and len(set(results)) == 1
    print(f"continuous_validation={'PASS' if stable else 'FAIL'} iterations={len(results)}")
    return 0 if stable else 1


if __name__ == "__main__":
    raise SystemExit(main())
