#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 SEALED_CASES_JSON EMPTY_OUTPUT_DIR UNLOCKED_ORACLE_JSON" >&2
  exit 64
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CASES_PATH="$1"
OUTPUT_DIR="$2"
ORACLE_PATH="$3"

cd "$REPO_ROOT"

# Phase 1: oracle remains inaccessible. The independent custodian should not
# place ORACLE_PATH on this host until inference and sealing have completed.
if [[ -e "$ORACLE_PATH" ]]; then
  echo "NO-GO: unlocked oracle must not exist before inference" >&2
  exit 1
fi

.venv/bin/python blind_v10/check_go_nogo.py \
  --cases "$CASES_PATH" \
  --output-dir "$OUTPUT_DIR"

.venv/bin/python blind_v10/runner/run_v10.py \
  --cases "$CASES_PATH" \
  --output-dir "$OUTPUT_DIR"

echo "Predictions are sealed. Independent custodian may now unlock: $ORACLE_PATH"
echo "Then run the frozen evaluator exactly once:"
echo ".venv/bin/python blind_v10/evaluator/evaluate_v10.py --predictions '$OUTPUT_DIR/predictions.jsonl' --cases '$CASES_PATH' --seal '$OUTPUT_DIR/predictions.seal.json' --oracle '$ORACLE_PATH' --output '$OUTPUT_DIR/final_report.json'"
