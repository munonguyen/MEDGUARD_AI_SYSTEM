from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.external_evidence_registry import (
    evaluate_external_evidence_registry,
    load_external_evidence_registry,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    registry = load_external_evidence_registry(args.registry)
    result = evaluate_external_evidence_registry(registry)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"external_evidence={result['status'].upper()} "
            f"valid={len(result['valid_types'])}/{len(result['required_types'])} "
            f"blockers={len(result['blockers'])}"
        )
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
