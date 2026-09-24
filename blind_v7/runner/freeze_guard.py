"""Freeze Guard for MedGuard AI Blind Benchmark V7.

Computes and verifies cryptographic hashes of sensitive core files to guarantee
that candidate code has not been altered or tuned between freeze and evaluation.
Includes all 19 core clinical engine files.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any

# 19 Sensitive core files defining the frozen MedGuard candidate V7 engine
SENSITIVE_FILES: tuple[str, ...] = (
    "app/models/clinical_events.py",
    "app/models/physiologic_consequences.py",
    "app/services/clinical_fact_parser.py",
    "app/services/clinical_threat_graph.py",
    "app/services/physiologic_consequence_engine.py",
    "app/services/toxicology_reasoner.py",
    "app/services/clinical_event_ledger.py",
    "app/services/compositional_reasoner.py",
    "app/services/semantic_risk.py",
    "app/services/dose_reasoning.py",
    "app/services/triage.py",
    "app/services/triage_resolver.py",
    "app/services/risk_memory.py",
    "app/services/rules.py",
    "app/services/chat.py",
    "app/services/ood_guard.py",
    "app/services/clinical_text.py",
    "app/knowledge/medication_incident_protocols.json",
    "app/knowledge/red_flag_protocols.json",
)


def compute_file_sha256(file_path: Path | str) -> str:
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Cannot hash non-existent file: {p}")
    h = sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_git_commit(repo_root: Path) -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_GIT_COMMIT"


def build_freeze_manifest(repo_root: Path) -> dict[str, Any]:
    file_hashes = {}
    for rel_path in SENSITIVE_FILES:
        full_path = repo_root / rel_path
        file_hashes[rel_path] = compute_file_sha256(full_path)

    return {
        "model_version": "medguard-candidate-v7-frozen",
        "git_commit": get_git_commit(repo_root),
        "file_hashes": file_hashes,
    }


def save_freeze_manifest(repo_root: Path, target_path: Path) -> dict[str, Any]:
    manifest = build_freeze_manifest(repo_root)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    return manifest


def verify_freeze_integrity(repo_root: Path, manifest_path: Path) -> tuple[bool, list[str]]:
    """Verify that current workspace files exactly match the freeze manifest."""
    if not manifest_path.exists():
        return False, [f"Freeze manifest not found at {manifest_path}"]

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    violations = []
    saved_hashes = manifest.get("file_hashes", {})

    for rel_path in SENSITIVE_FILES:
        if rel_path not in saved_hashes:
            violations.append(f"Missing expected hash for sensitive file: {rel_path}")
            continue
        full_path = repo_root / rel_path
        if not full_path.exists():
            violations.append(f"Sensitive file missing from workspace: {rel_path}")
            continue
        curr_hash = compute_file_sha256(full_path)
        if curr_hash != saved_hashes[rel_path]:
            violations.append(
                f"Hash mismatch on sensitive file '{rel_path}':\n"
                f"  Frozen:  {saved_hashes[rel_path]}\n"
                f"  Current: {curr_hash}"
            )

    return len(violations) == 0, violations
