"""Compile governed raw samples into deterministic role-specific SFT splits."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable

from training.contracts import AnswerTrainingSample, TrainingSample, parse_training_sample


_PII_PATTERNS = {
    "email": re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"(?<!\d)(?:\+?84|0)(?:\s?\d){8,10}(?!\d)"),
    "national_id": re.compile(r"(?<!\d)\d{12}(?!\d)"),
    "patient_reference": re.compile(r"\b(?:BN|HS|PATIENT|P)[-_][A-Z0-9][A-Z0-9._-]*\b", re.I),
}

_APPROVED_PLACEHOLDER = re.compile(
    r"\[(?:PATIENT_REF|EMAIL|PHONE|NATIONAL_ID|NAME|DATE_OF_BIRTH|ADDRESS)\]"
)

_SYSTEM_PROMPTS = {
    "answer": (
        "Follow the MedGuard answer contract. Use supplied tool results and evidence only. "
        "Preserve locked claims exactly, express uncertainty, and never diagnose or prescribe."
    ),
    "verifier": (
        "Follow the MedGuard verifier contract. Compare the candidate with immutable claims "
        "and evidence, then return the reviewed verdict without adding medical advice."
    ),
}


class DatasetValidationError(ValueError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _all_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _all_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_strings(item)


def _validate_governance(sample: TrainingSample) -> None:
    if not sample.deidentified:
        raise DatasetValidationError(f"{sample.sample_id}: deidentified must be true")
    if sample.expert_review.status != "approved":
        raise DatasetValidationError(f"{sample.sample_id}: expert review is not approved")
    if not sample.provenance.usage_rights_confirmed:
        raise DatasetValidationError(f"{sample.sample_id}: data usage rights are not confirmed")
    if sample.provenance.source_kind == "external_evaluation":
        raise DatasetValidationError(f"{sample.sample_id}: external evaluation data cannot enter training")
    serialized = sample.model_dump(mode="json")
    for text in _all_strings(serialized):
        text = _APPROVED_PLACEHOLDER.sub("", text)
        for label, pattern in _PII_PATTERNS.items():
            if pattern.search(text):
                raise DatasetValidationError(f"{sample.sample_id}: possible {label} remains")


def _content_fingerprint(sample: TrainingSample) -> str:
    value = sample.model_dump(mode="json", exclude={"sample_id", "case_group_id", "expert_review"})
    normalized = re.sub(r"\s+", " ", _canonical(value).strip().lower())
    return _sha256_bytes(normalized.encode("utf-8"))


def assigned_split(case_group_id: str, seed: str = "medguard-split-v1") -> str:
    bucket = int(sha256(f"{seed}:{case_group_id}".encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < 80:
        return "train"
    if bucket < 90:
        return "validation"
    return "test"


def validate_samples(samples: list[TrainingSample]) -> dict[str, Any]:
    if not samples:
        raise DatasetValidationError("dataset contains no samples")
    ids: set[str] = set()
    fingerprints: set[str] = set()
    groups: dict[str, str] = {}
    role_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    role_split_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    verifier_verdict_counts: Counter[str] = Counter()
    for sample in samples:
        _validate_governance(sample)
        if sample.sample_id in ids:
            raise DatasetValidationError(f"duplicate sample_id: {sample.sample_id}")
        ids.add(sample.sample_id)
        fingerprint = _content_fingerprint(sample)
        if fingerprint in fingerprints:
            raise DatasetValidationError(f"{sample.sample_id}: duplicate normalized training content")
        fingerprints.add(fingerprint)
        split = assigned_split(sample.case_group_id)
        previous = groups.setdefault(sample.case_group_id, split)
        if previous != split:
            raise DatasetValidationError(f"{sample.case_group_id}: case group leaked across splits")
        role_counts[sample.role] += 1
        split_counts[split] += 1
        role_split_counts[f"{sample.role}:{split}"] += 1
        category_counts[f"{sample.role}:{sample.task_category}"] += 1
        if sample.role == "verifier":
            verifier_verdict_counts["approved" if sample.target.approved else "rejected"] += 1
    return {
        "sample_count": len(samples),
        "role_counts": dict(sorted(role_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "role_split_counts": dict(sorted(role_split_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "verifier_verdict_counts": dict(sorted(verifier_verdict_counts.items())),
        "unique_case_groups": len(groups),
        "duplicate_count": 0,
        "external_evaluation_count": 0,
        "possible_pii_count": 0,
    }


def load_jsonl(path: Path) -> list[TrainingSample]:
    samples: list[TrainingSample] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("record is not an object")
            samples.append(parse_training_sample(value))
        except (json.JSONDecodeError, ValueError) as exc:
            raise DatasetValidationError(f"{path}:{line_number}: {exc}") from exc
    return samples


def _sft_record(sample: TrainingSample) -> dict[str, Any]:
    source = sample.model_dump(
        mode="json",
        exclude={
            "schema_version",
            "sample_id",
            "case_group_id",
            "role",
            "task_category",
            "deidentified",
            "provenance",
            "expert_review",
            "target",
        },
    )
    return {
        "sample_id": sample.sample_id,
        "case_group_id": sample.case_group_id,
        "role": sample.role,
        "task_category": sample.task_category,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPTS[sample.role]},
            {"role": "user", "content": _canonical(source)},
            {
                "role": "assistant",
                "content": _canonical(sample.target.model_dump(mode="json")),
            },
        ],
    }


def _dataset_gate_failures(validation: dict[str, Any], gate: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for role, requirements in gate.get("roles", {}).items():
        minimum_samples = int(requirements.get("minimum_samples", 0))
        if validation["role_counts"].get(role, 0) < minimum_samples:
            failures.append(f"{role}:sample_count<{minimum_samples}")
        for split, minimum in requirements.get("minimum_split_samples", {}).items():
            if validation["role_split_counts"].get(f"{role}:{split}", 0) < int(minimum):
                failures.append(f"{role}:{split}<{minimum}")
        for category, minimum in requirements.get("minimum_category_samples", {}).items():
            if validation["category_counts"].get(f"{role}:{category}", 0) < int(minimum):
                failures.append(f"{role}:{category}<{minimum}")
    for verdict, minimum in gate.get("verifier_minimum_verdict_samples", {}).items():
        if validation["verifier_verdict_counts"].get(verdict, 0) < int(minimum):
            failures.append(f"verifier:{verdict}<{minimum}")
    return failures


def compile_dataset(
    source_path: Path,
    output_dir: Path,
    dataset_version: str,
    gate_path: Path | None = None,
) -> dict[str, Any]:
    samples = load_jsonl(source_path)
    validation = validate_samples(samples)
    output_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, dict[str, Any]] = {}
    for role in ("answer", "verifier"):
        for split in ("train", "validation", "test"):
            records = [
                _sft_record(sample)
                for sample in samples
                if sample.role == role and assigned_split(sample.case_group_id) == split
            ]
            if not records:
                continue
            body = "".join(_canonical(record) + "\n" for record in records).encode("utf-8")
            filename = f"{role}-{split}.jsonl"
            (output_dir / filename).write_bytes(body)
            files[filename] = {"sha256": _sha256_bytes(body), "records": len(records)}
    source_bytes = source_path.read_bytes()
    effective_gate_path = gate_path or Path(__file__).with_name("dataset_gate.json")
    gate_bytes = effective_gate_path.read_bytes()
    gate = json.loads(gate_bytes)
    if gate.get("schema_version") != "medguard.dataset-gate.v1":
        raise DatasetValidationError("unsupported dataset gate schema")
    gate_failures = _dataset_gate_failures(validation, gate)
    manifest = {
        "schema_version": "medguard.training-manifest.v1",
        "dataset_version": dataset_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_sha256": _sha256_bytes(source_bytes),
        "dataset_gate_sha256": _sha256_bytes(gate_bytes),
        "split_strategy": "sha256(case_group_id,medguard-split-v1):80/10/10",
        "validation": validation,
        "dataset_gate_failures": gate_failures,
        "files": files,
        "approved_for_sft": bool(files) and not gate_failures,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def validate_compiled_manifest(path: Path, *, role: str | None = None) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "medguard.training-manifest.v1":
        raise DatasetValidationError("unsupported training manifest schema")
    if not manifest.get("approved_for_sft"):
        raise DatasetValidationError("dataset manifest is not approved for SFT")
    for filename, descriptor in manifest.get("files", {}).items():
        if role and not filename.startswith(f"{role}-"):
            continue
        candidate = path.parent / filename
        if not candidate.is_file():
            raise DatasetValidationError(f"compiled dataset is missing: {filename}")
        if _sha256_bytes(candidate.read_bytes()) != descriptor.get("sha256"):
            raise DatasetValidationError(f"compiled dataset checksum mismatch: {filename}")
    if role and not any(name.startswith(f"{role}-train") for name in manifest.get("files", {})):
        raise DatasetValidationError(f"manifest has no training split for role: {role}")
    return manifest
