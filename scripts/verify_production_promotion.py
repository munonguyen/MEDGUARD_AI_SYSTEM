"""Fail-closed verifier for a MedGuard production promotion candidate.

This tool consumes an already-generated release evidence manifest. It does not
create approvals, mutate evidence, contact providers, or deploy anything. A
candidate passes only when the manifest is intact, explicitly production
eligible, blocker-free, and bound to the expected code SHA.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.generate_release_evidence import validate_release_evidence


def verify_production_promotion(
    payload: dict[str, Any],
    *,
    expected_code_sha: str,
) -> tuple[bool, list[str]]:
    errors: list[str] = []

    valid, manifest_errors = validate_release_evidence(payload)
    if not valid:
        errors.extend(f"manifest:{item}" for item in manifest_errors)

    actual_sha = str(payload.get("code_sha") or "").strip()
    expected_sha = expected_code_sha.strip()
    if not expected_sha:
        errors.append("missing_expected_code_sha")
    elif actual_sha != expected_sha:
        errors.append("candidate_code_sha_mismatch")

    blockers = payload.get("release_blockers")
    if not isinstance(blockers, list):
        errors.append("release_blockers_missing_or_invalid")
    elif blockers:
        errors.append("release_blockers_present")

    if payload.get("production_release_eligible") is not True:
        errors.append("production_release_not_eligible")

    external = payload.get("external_production_evidence") or {}
    if external.get("valid") is not True:
        errors.append("external_production_evidence_not_valid")

    clinical = payload.get("clinical_validation") or {}
    if clinical.get("status") != "pass":
        errors.append("independent_clinical_validation_not_passed")

    readiness = payload.get("readiness") or {}
    if readiness.get("production_ready") is not True:
        errors.append("runtime_production_readiness_not_passed")

    quality = payload.get("quality") or {}
    if (quality.get("medical_response") or {}).get("gate_passed") is not True:
        errors.append("medical_response_quality_not_passed")
    if (quality.get("professional_response") or {}).get("gate_passed") is not True:
        errors.append("professional_response_quality_not_passed")

    return not errors, sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path, help="Release evidence JSON to verify.")
    parser.add_argument(
        "--expected-code-sha",
        required=True,
        help="Exact candidate commit SHA that the evidence must bind to.",
    )
    args = parser.parse_args()

    try:
        payload = json.loads(args.evidence.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"production_promotion=BLOCKED errors=evidence_unreadable:{exc.__class__.__name__}")
        return 2
    if not isinstance(payload, dict):
        print("production_promotion=BLOCKED errors=evidence_root_not_object")
        return 2

    passed, errors = verify_production_promotion(
        payload,
        expected_code_sha=args.expected_code_sha,
    )
    print(
        f"production_promotion={'ALLOWED' if passed else 'BLOCKED'} "
        f"candidate_sha={args.expected_code_sha} "
        f"errors={','.join(errors) or 'none'}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
