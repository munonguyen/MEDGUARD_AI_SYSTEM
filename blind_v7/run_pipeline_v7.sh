#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "================================================================================"
echo " MEDGUARD AI — BLIND BENCHMARK V7 AUTOMATED ONE-SHOT PIPELINE"
echo "================================================================================"

echo "[1/3] Running Pre-Flight Go/No-Go Audit..."
.venv/bin/python3 blind_v7/check_go_nogo.py blind_v7/sealed_cases/cases.json 300

mkdir -p blind_v7/outputs

echo ""
echo "[2/3] Executing Blind V7 Sealed Inference Runner..."
.venv/bin/python3 blind_v7/runner/run_v7.py 2>&1 | tee blind_v7/outputs/runner_stdout.log

echo ""
echo "[3/3] Executing Blind V7 Post-Hoc Evaluator..."
.venv/bin/python3 blind_v7/evaluator/evaluate_v7.py 2>&1 | tee blind_v7/outputs/evaluator_stdout.log

echo ""
echo "================================================================================"
echo " BLIND BENCHMARK V7 PIPELINE COMPLETE"
echo "================================================================================"
