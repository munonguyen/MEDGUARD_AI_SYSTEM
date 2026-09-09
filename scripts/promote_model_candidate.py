"""Promote an evaluated and approved adapter into the offline model registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from training.model_registry import ModelPromotionError, promote_candidate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-manifest", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--evaluation-report", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument(
        "--registry",
        type=Path,
        default=BASE_DIR / "training" / "registry" / "models.json",
    )
    args = parser.parse_args()
    try:
        record = promote_candidate(
            artifact_manifest_path=args.artifact_manifest,
            dataset_manifest_path=args.dataset_manifest,
            evaluation_report_path=args.evaluation_report,
            approval_path=args.approval,
            registry_path=args.registry,
        )
    except (OSError, ValueError, ModelPromotionError) as exc:
        print(f"model promotion rejected: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(record, indent=2))
    print("Registry updated. Live LiteLLM routing was not changed automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
