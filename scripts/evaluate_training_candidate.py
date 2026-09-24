"""Evaluate held-out predictions against the versioned model release gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from training.evaluation import EvaluationError, evaluate_predictions  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("answer", "verifier"), required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument(
        "--gate",
        type=Path,
        default=BASE_DIR / "training" / "evaluation_gate.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = evaluate_predictions(
            args.predictions,
            args.gate,
            args.role,
            args.dataset_manifest,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, EvaluationError) as exc:
        print(f"candidate evaluation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
