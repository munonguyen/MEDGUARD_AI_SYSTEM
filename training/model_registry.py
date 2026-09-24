"""Checksum-bound model candidate promotion without changing live routing."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


class ModelPromotionError(ValueError):
    pass


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ModelPromotionError(f"{path}: expected a JSON object")
    return value


def build_artifact_manifest(
    *,
    output_dir: Path,
    model_id: str,
    role: str,
    base_model: str,
    base_revision: str,
    dataset_manifest_path: Path,
    training_config_path: Path,
) -> dict[str, Any]:
    files: dict[str, str] = {}
    for candidate in sorted(output_dir.rglob("*")):
        if candidate.is_file() and candidate.name != "artifact-manifest.json":
            relative = str(candidate.relative_to(output_dir))
            files[relative] = file_sha256(candidate)
    if not files:
        raise ModelPromotionError("training output contains no adapter artifacts")
    return {
        "schema_version": "medguard.model-artifact.v1",
        "model_id": model_id,
        "role": role,
        "base_model": base_model,
        "base_revision": base_revision,
        "dataset_manifest_sha256": file_sha256(dataset_manifest_path),
        "training_config_sha256": file_sha256(training_config_path),
        "files": files,
    }


def _verify_artifacts(manifest_path: Path, manifest: dict[str, Any]) -> None:
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ModelPromotionError("artifact manifest contains no files")
    for relative, expected in files.items():
        path = manifest_path.parent / str(relative)
        if not path.is_file():
            raise ModelPromotionError(f"model artifact is missing: {relative}")
        if file_sha256(path) != expected:
            raise ModelPromotionError(f"model artifact checksum mismatch: {relative}")


def promote_candidate(
    *,
    artifact_manifest_path: Path,
    dataset_manifest_path: Path,
    evaluation_report_path: Path,
    approval_path: Path,
    registry_path: Path,
) -> dict[str, Any]:
    artifact = _read_object(artifact_manifest_path)
    dataset = _read_object(dataset_manifest_path)
    evaluation = _read_object(evaluation_report_path)
    approval = _read_object(approval_path)
    if artifact.get("schema_version") != "medguard.model-artifact.v1":
        raise ModelPromotionError("unsupported model artifact schema")
    if dataset.get("schema_version") != "medguard.training-manifest.v1":
        raise ModelPromotionError("unsupported dataset manifest schema")
    if dataset.get("approved_for_sft") is not True or dataset.get("dataset_gate_failures"):
        raise ModelPromotionError("dataset manifest is not approved for SFT")
    if evaluation.get("schema_version") != "medguard.evaluation-report.v1":
        raise ModelPromotionError("unsupported evaluation report schema")
    if approval.get("schema_version") != "medguard.model-approval.v1":
        raise ModelPromotionError("unsupported model approval schema")
    _verify_artifacts(artifact_manifest_path, artifact)
    if artifact.get("dataset_manifest_sha256") != file_sha256(dataset_manifest_path):
        raise ModelPromotionError("artifact is not bound to this dataset manifest")
    model_id = str(artifact.get("model_id", ""))
    role = str(artifact.get("role", ""))
    if role not in {"answer", "verifier"} or not model_id.startswith(f"medguard-{role}-v"):
        raise ModelPromotionError("model ID must be versioned and match its role")
    if evaluation.get("candidate_model_id") != model_id or evaluation.get("role") != role:
        raise ModelPromotionError("evaluation report belongs to another model or role")
    if evaluation.get("dataset_manifest_sha256") != file_sha256(dataset_manifest_path):
        raise ModelPromotionError("evaluation report is not bound to this dataset manifest")
    if not evaluation.get("passed") or evaluation.get("failures"):
        raise ModelPromotionError("candidate did not pass the evaluation gate")
    if approval.get("model_id") != model_id or approval.get("status") != "approved":
        raise ModelPromotionError("candidate has no matching approved review")
    if approval.get("approver_role") not in {"clinical_safety", "model_risk_committee"}:
        raise ModelPromotionError("candidate approval role is not authorized")
    if not str(approval.get("approval_id", "")).startswith("approval-"):
        raise ModelPromotionError("candidate approval ID is invalid")

    registry = (
        _read_object(registry_path)
        if registry_path.exists()
        else {
            "schema_version": "medguard.model-registry.v1",
            "aliases": {"answer": None, "verifier": None},
            "models": [],
        }
    )
    if registry.get("schema_version") != "medguard.model-registry.v1":
        raise ModelPromotionError("unsupported model registry schema")
    if any(item.get("model_id") == model_id for item in registry.get("models", [])):
        raise ModelPromotionError("model candidate is already registered")
    previous = registry.setdefault("aliases", {}).get(role)
    record = {
        "model_id": model_id,
        "role": role,
        "status": "approved_candidate",
        "base_model": artifact.get("base_model"),
        "base_revision": artifact.get("base_revision"),
        "artifact_manifest_sha256": file_sha256(artifact_manifest_path),
        "dataset_manifest_sha256": file_sha256(dataset_manifest_path),
        "evaluation_report_sha256": file_sha256(evaluation_report_path),
        "approval_sha256": file_sha256(approval_path),
        "approval_id": approval.get("approval_id"),
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "rollback_model_id": previous,
    }
    registry.setdefault("models", []).append(record)
    registry["aliases"][role] = model_id
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = registry_path.with_suffix(registry_path.suffix + ".tmp")
    temporary.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    temporary.replace(registry_path)
    return record
