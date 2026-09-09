"""Validate licensed external dataset files without loading patient rows into logs."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "datasets" / "external" / "mimic-iv-ed-demo-2.2"
REQUIRED_TRIAGE_COLUMNS = {
    "subject_id",
    "stay_id",
    "temperature",
    "heartrate",
    "resprate",
    "o2sat",
    "sbp",
    "dbp",
    "acuity",
    "chiefcomplaint",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_mimic_demo(dataset_dir: Path = DATASET_DIR) -> dict[str, Any]:
    manifest_path = dataset_dir / "manifest.json"
    checksums_path = dataset_dir / "SHA256SUMS.txt"
    errors: list[str] = []
    if not manifest_path.is_file() or not checksums_path.is_file():
        return {"dataset": dataset_dir.name, "valid": False, "errors": ["manifest or checksum file missing"]}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected: dict[str, str] = {}
    for line in checksums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            errors.append("invalid checksum line")
            continue
        expected[parts[1].lstrip("*")] = parts[0]

    checked = 0
    for relative_name, expected_hash in expected.items():
        path = dataset_dir / relative_name
        if not path.is_file():
            errors.append(f"missing file: {relative_name}")
            continue
        checked += 1
        if _sha256(path) != expected_hash:
            errors.append(f"checksum mismatch: {relative_name}")

    triage_path = dataset_dir / "ed" / "triage.csv.gz"
    row_count = 0
    if triage_path.is_file():
        try:
            with gzip.open(triage_path, "rt", encoding="utf-8", newline="") as stream:
                header = set(stream.readline().strip().split(","))
                row_count = sum(1 for _ in stream)
            missing_columns = REQUIRED_TRIAGE_COLUMNS - header
            if missing_columns:
                errors.append(f"triage columns missing: {sorted(missing_columns)}")
        except (OSError, UnicodeError) as exc:
            errors.append(f"triage gzip invalid: {exc.__class__.__name__}")
    if row_count != manifest.get("expected_triage_rows"):
        errors.append(
            f"triage row count {row_count} != {manifest.get('expected_triage_rows')}"
        )
    return {
        "dataset": manifest.get("dataset_id", dataset_dir.name),
        "valid": not errors,
        "checked_files": checked,
        "triage_rows": row_count,
        "production_evaluable": bool(manifest.get("production_evaluable", False)),
        "errors": errors,
    }


def main() -> int:
    report = validate_mimic_demo()
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
