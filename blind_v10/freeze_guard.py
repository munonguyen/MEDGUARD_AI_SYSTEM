"""Generate and verify the immutable MedGuard Candidate V10 attestation."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "blind_v10" / "freeze_manifest.json"
MECHANISM_REPORT = REPO_ROOT / "outputs" / "v10_mechanism_benchmarks_report.json"
REGRESSION_REPORT = REPO_ROOT / "outputs" / "v10_regression_2400_report.json"
CORE_TAG = "v10-candidate-core"
FROZEN_TAG = "v10-blind-frozen"

CORE_FILES: tuple[str, ...] = (
    "app/services/chat.py",
    "app/services/clinical_safety_floor.py",
    "app/services/dual_crisis_policy.py",
    "app/services/end_organ_coupling.py",
    "app/services/ood_guard.py",
    "app/services/response_safety.py",
    "app/services/rules.py",
    "app/services/toxicology_signature_router.py",
    "app/services/triage.py",
)

FROZEN_FILES: tuple[str, ...] = CORE_FILES + (
    "app/services/evidence_strength_scorer.py",
    "app/services/clinical_fact_parser.py",
    "app/services/clinical_threat_graph.py",
    "app/services/physiologic_consequence_engine.py",
    "app/services/triage_resolver.py",
    "app/services/jev_engine.py",
    "app/services/jev_governance.py",
    "app/services/tri_gate_orchestrator.py",
    "app/services/tri_gate_resolver.py",
    "app/tests/test_candidate_v10_architecture.py",
    "app/tests/test_v10_freeze_guard.py",
    "blind_v10/README.md",
    "blind_v10/check_go_nogo.py",
    "blind_v10/evaluator/evaluate_v10.py",
    "blind_v10/freeze_guard.py",
    "blind_v10/runner/run_v10.py",
    "blind_v10/run_one_shot.sh",
    "blind_v10/seal.py",
    "docs/CANDIDATE_V10_IMPLEMENTATION.md",
    "scripts/run_1800_regression.py",
    "scripts/run_v10_regression_2400.py",
    "tests/benchmarks/benchmark_candidate_v10.py",
)


def _hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def _git_commit(ref: str = "HEAD") -> str:
    try:
        return _git("rev-parse", f"{ref}^{{commit}}")
    except Exception:
        return "UNKNOWN_COMMIT"


def _git_blob_hash(ref: str, path: str) -> str:
    blob = subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=REPO_ROOT)
    return sha256(blob).hexdigest()


def _canonical_manifest_sha256(manifest: dict[str, Any]) -> str:
    """Hash a canonical payload excluding only its self-hash field."""
    payload = deepcopy(manifest)
    payload.pop("freeze_manifest_sha256", None)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def _load_prerequisites() -> tuple[dict[str, Any], dict[str, Any]]:
    mechanism = json.loads(MECHANISM_REPORT.read_text(encoding="utf-8"))
    regression = json.loads(REGRESSION_REPORT.read_text(encoding="utf-8"))
    if mechanism.get("total_cases") != 180 or not mechanism.get("all_release_gates_passed"):
        raise RuntimeError("V10 mechanism prerequisite has not passed exactly 180 cases")
    if regression.get("total_cases") != 2400 or not regression.get("all_release_gates_passed"):
        raise RuntimeError("V10 regression prerequisite has not passed exactly 2,400 cases")
    if regression.get("pure_t4_to_routine") != 0 or regression.get("pure_t4_to_urgent") != 0:
        raise RuntimeError("V10 regression contains Pure-T4 under-triage")
    if float(regression.get("specificity_pct", 0.0)) < 95.0:
        raise RuntimeError("V10 regression specificity is below 95%")
    if regression.get("unsafe_response_content") != 0:
        raise RuntimeError("V10 regression contains unsafe response content")
    if regression.get("system_errors") != 0:
        raise RuntimeError("V10 regression contains system errors")
    return mechanism, regression


def _assert_core_matches_tag(file_hashes: dict[str, str]) -> dict[str, bool]:
    if _git_commit(CORE_TAG) == "UNKNOWN_COMMIT":
        raise RuntimeError(f"missing immutable core tag: {CORE_TAG}")
    preserved = {
        path: file_hashes[path] == _git_blob_hash(CORE_TAG, path)
        for path in CORE_FILES
    }
    if not all(preserved.values()):
        raise RuntimeError(f"clinical core differs from {CORE_TAG}: {preserved}")
    return preserved


def _assert_jev_preserved(file_hashes: dict[str, str]) -> dict[str, bool]:
    v9_manifest = json.loads(
        (REPO_ROOT / "blind_v9" / "freeze_manifest.json").read_text(encoding="utf-8")
    )
    v9_hashes = v9_manifest.get("file_hashes", {})
    preserved = {
        path: file_hashes[path] == v9_hashes.get(path)
        for path in ("app/services/jev_engine.py", "app/services/jev_governance.py")
    }
    if not all(preserved.values()):
        raise RuntimeError(f"Jev Gate 3 changed since V9 freeze: {preserved}")
    return preserved


def generate_freeze_manifest(
    *,
    blind_frozen_commit: str | None = None,
) -> dict[str, Any]:
    mechanism, regression = _load_prerequisites()
    missing = [path for path in FROZEN_FILES if not (REPO_ROOT / path).exists()]
    if missing:
        raise RuntimeError(f"frozen files missing: {missing}")
    file_hashes = {path: _hash(REPO_ROOT / path) for path in FROZEN_FILES}
    core_preserved = _assert_core_matches_tag(file_hashes)
    jev_preserved = _assert_jev_preserved(file_hashes)
    combined = sha256(
        "\n".join(
            f"{path}:{file_hashes[path]}" for path in sorted(file_hashes)
        ).encode("utf-8")
    ).hexdigest()
    manifest: dict[str, Any] = {
        "candidate": "MedGuard-V10",
        "status": "FROZEN_FOR_INDEPENDENT_BLIND_V10_ONE_SHOT_VALIDATION",
        "clinical_generalization_confirmed": False,
        "blind_v10_executed": False,
        "candidate_core_commit": _git_commit(CORE_TAG),
        # This is the audit baseline commit. The v10-blind-frozen annotated tag
        # points to its single provenance child containing this manifest.
        "blind_frozen_commit": blind_frozen_commit or _git_commit("HEAD"),
        "attestation_model": "tagged_provenance_child_of_blind_frozen_commit",
        "generated_from_head": _git_commit("HEAD"),
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "core_manifest_sha256": combined,
        "mechanism_benchmark_sha256": _hash(MECHANISM_REPORT),
        "regression_report_sha256": _hash(REGRESSION_REPORT),
        "pre_blind_gates": {
            "mechanism_cases": mechanism["total_cases"],
            "mechanism_all_passed": mechanism["all_release_gates_passed"],
            "regression_cases": regression["total_cases"],
            "pure_t4_sensitivity_pct": regression["pure_t4_sensitivity_pct"],
            "pure_t4_to_urgent": regression["pure_t4_to_urgent"],
            "pure_t4_to_routine": regression["pure_t4_to_routine"],
            "specificity_pct": regression["specificity_pct"],
            "unsafe_response_content": regression["unsafe_response_content"],
            "system_errors": regression["system_errors"],
        },
        "clinical_core_matches_candidate_tag": core_preserved,
        "jev_gate3_preserved_from_v9": jev_preserved,
        "excluded_pre_existing_artifacts": [
            {
                "path": "datasets/active_learning/captured_cases.json",
                "reason": "pre-existing mutable telemetry; excluded from candidate and freeze scope",
            }
        ],
        "file_hashes": file_hashes,
    }
    manifest["freeze_manifest_sha256"] = _canonical_manifest_sha256(manifest)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify_freeze_integrity(
    path: Path = MANIFEST_PATH,
    *,
    require_frozen_tag: bool = True,
) -> tuple[bool, list[str]]:
    if not path.exists():
        return False, [f"missing manifest: {path}"]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []

    expected_self_hash = manifest.get("freeze_manifest_sha256")
    if _canonical_manifest_sha256(manifest) != expected_self_hash:
        errors.append("freeze manifest canonical SHA-256 mismatch")
    for rel_path, expected in manifest.get("file_hashes", {}).items():
        candidate = REPO_ROOT / rel_path
        if not candidate.exists():
            errors.append(f"missing frozen file: {rel_path}")
        elif _hash(candidate) != expected:
            errors.append(f"hash mismatch: {rel_path}")
    if _hash(MECHANISM_REPORT) != manifest.get("mechanism_benchmark_sha256"):
        errors.append("mechanism benchmark report changed")
    if _hash(REGRESSION_REPORT) != manifest.get("regression_report_sha256"):
        errors.append("2,400-case regression report changed")

    core_commit = _git_commit(CORE_TAG)
    if core_commit != manifest.get("candidate_core_commit"):
        errors.append(f"{CORE_TAG} does not match candidate_core_commit")
    for rel_path in CORE_FILES:
        try:
            if _hash(REPO_ROOT / rel_path) != _git_blob_hash(CORE_TAG, rel_path):
                errors.append(f"clinical core differs from {CORE_TAG}: {rel_path}")
        except Exception:
            errors.append(f"unable to verify core-tag blob: {rel_path}")

    baseline_commit = str(manifest.get("blind_frozen_commit", ""))
    if baseline_commit == "UNKNOWN_COMMIT" or not baseline_commit:
        errors.append("blind_frozen_commit is not immutable")
    if require_frozen_tag:
        tagged_commit = _git_commit(FROZEN_TAG)
        if tagged_commit == "UNKNOWN_COMMIT":
            errors.append(f"missing immutable frozen tag: {FROZEN_TAG}")
        else:
            try:
                tagged_parent = _git("rev-parse", f"{FROZEN_TAG}^{{commit}}^")
                if tagged_parent != baseline_commit:
                    errors.append(
                        f"{FROZEN_TAG} is not the provenance child of blind_frozen_commit"
                    )
            except Exception:
                errors.append(f"unable to verify {FROZEN_TAG} attestation chain")
    return not errors, errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify",
        action="store_true",
        help="verify the existing manifest without rewriting it",
    )
    parser.add_argument(
        "--blind-frozen-commit",
        help="audit baseline commit that the provenance commit will attest",
    )
    parser.add_argument(
        "--allow-missing-frozen-tag",
        action="store_true",
        help="only for constructing the provenance commit before its tag exists",
    )
    args = parser.parse_args()
    if args.verify:
        valid, violations = verify_freeze_integrity(
            require_frozen_tag=not args.allow_missing_frozen_tag
        )
        print(json.dumps({"valid": valid, "violations": violations}, indent=2))
        raise SystemExit(0 if valid else 1)
    generated = generate_freeze_manifest(
        blind_frozen_commit=args.blind_frozen_commit
    )
    print(json.dumps(generated, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
