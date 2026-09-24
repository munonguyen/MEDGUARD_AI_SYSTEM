#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "================================================================================"
echo " MEDGUARD AI — BLIND BENCHMARK V6 AUTOMATED ONE-SHOT PIPELINE"
echo "================================================================================"

echo "[1/3] Running Pre-Flight Go/No-Go Audit..."
.venv/bin/python3 blind_v6/check_go_nogo.py blind_v6/sealed_cases/cases.json 300

echo ""
echo "[2/3] Executing Blind V6 Sealed Inference Runner..."
.venv/bin/python3 blind_v6/runner/run_v6.py 2>&1 | tee blind_v6/outputs/runner_stdout.log

echo ""
echo "[3/3] Executing Blind V6 Post-Hoc Evaluator..."
.venv/bin/python3 blind_v6/evaluator/evaluate_v6.py 2>&1 | tee blind_v6/outputs/evaluator_stdout.log

echo ""
echo "================================================================================"
echo " BLIND BENCHMARK V6 PIPELINE COMPLETE"
echo "================================================================================"
