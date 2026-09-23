#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "================================================================================"
echo "MEDGUARD AI BLIND BENCHMARK V9 — ONE-SHOT VALIDATION PIPELINE"
echo "Candidate: MedGuard-V9 (v9-candidate-core, v9-blind-frozen)"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "================================================================================"

echo ""
echo ">>> STEP 1: Verify Freeze Integrity and Regenerate Manifest if needed <<<"
.venv/bin/python3 blind_v9/freeze_guard.py

echo ""
echo ">>> STEP 2: Pre-Flight GO / NO-GO Audit <<<"
.venv/bin/python3 blind_v9/check_go_nogo.py

echo ""
echo ">>> STEP 3: Execute Sealed One-Shot Inference (300 cases, ZERO Oracle access) <<<"
.venv/bin/python3 blind_v9/runner/run_v9.py

echo ""
echo ">>> STEP 4: Run Evaluation Against Cryptographically Unlocked Oracle <<<"
.venv/bin/python3 blind_v9/evaluator/evaluate_v9.py

echo ""
echo "================================================================================"
echo "BLIND BENCHMARK V9 PIPELINE COMPLETED SUCCESSFULLY"
echo "================================================================================"
