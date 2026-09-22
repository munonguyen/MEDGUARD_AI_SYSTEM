#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "================================================================================"
echo " MEDGUARD AI — BLIND BENCHMARK V8 AUTOMATED ONE-SHOT PIPELINE (TRI-GATE + JEV)"
echo "================================================================================"

echo "[1/3] Running Pre-Flight Go/No-Go Audit..."
.venv/bin/python3 blind_v8/check_go_nogo.py blind_v8/sealed_cases/cases.json 300

mkdir -p blind_v8/outputs

echo ""
echo "[2/3] Executing Blind V8 Sealed Inference Runner..."
.venv/bin/python3 blind_v8/runner/run_v8.py 2>&1 | tee blind_v8/outputs/runner_stdout.log

echo ""
echo "[3/3] Executing Blind V8 Post-Hoc Evaluator..."
.venv/bin/python3 blind_v8/evaluator/evaluate_v8.py 2>&1 | tee blind_v8/outputs/evaluator_stdout.log

echo ""
echo "================================================================================"
echo " BLIND BENCHMARK V8 PIPELINE COMPLETE"
echo "================================================================================"
