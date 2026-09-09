"""Validate governed JSONL and compile deterministic TRL-compatible splits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from training.dataset_pipeline import DatasetValidationError, compile_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument(
        "--gate",
        type=Path,
        default=BASE_DIR / "training" / "dataset_gate.json",
    )
    args = parser.parse_args()
    try:
        manifest = compile_dataset(args.source, args.output_dir, args.dataset_version, args.gate)
    except (OSError, ValueError, DatasetValidationError) as exc:
        print(f"training dataset rejected: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
