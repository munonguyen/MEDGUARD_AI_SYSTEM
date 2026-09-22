"""Freeze Guard for MedGuard AI Blind Benchmark V8 (Tri-Gate Candidate).

Computes and verifies cryptographic hashes of sensitive core files to guarantee
that candidate code has not been altered or tuned between freeze and evaluation.
Includes all 24 core clinical engine files covering Gates 0-3, Jev, and Knowledge.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any

# 24 Sensitive core files defining the frozen MedGuard candidate V8 engine
SENSITIVE_FILES: tuple[str, ...] = (
    "app/models/clinical_events.py",
    "app/models/physiologic_consequences.py",
    "app/models/jev.py",
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
    "app/services/jev_engine.py",
    "app/services/jev_governance.py",
    "app/services/tri_gate_orchestrator.py",
    "app/services/tri_gate_resolver.py",
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
        return "UNKNOWN_COMMIT"


def generate_freeze_manifest(repo_root: Path | str) -> dict[str, Any]:
    root = Path(repo_root)
    file_hashes: dict[str, str] = {}
    for rel_path in SENSITIVE_FILES:
        target = root / rel_path
        if not target.exists():
            raise FileNotFoundError(f"Missing core file for freeze manifest: {rel_path}")
        file_hashes[rel_path] = compute_file_sha256(target)

    commit = get_git_commit(root)
    return {
        "model_version": "medguard-candidate-v8-tri-gate-frozen",
        "git_commit": commit,
        "file_hashes": file_hashes,
    }


def verify_freeze_integrity(
    repo_root: Path | str,
    manifest_path: Path | str,
) -> tuple[bool, list[str]]:
    root = Path(repo_root)
    man_file = Path(manifest_path)
    if not man_file.exists():
        return False, [f"Manifest file not found: {man_file}"]

    with open(man_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    expected_hashes = manifest.get("file_hashes", {})
    violations: list[str] = []

    for rel_path in SENSITIVE_FILES:
        target = root / rel_path
        if not target.exists():
            violations.append(f"MISSING: {rel_path}")
            continue
        curr_hash = compute_file_sha256(target)
        exp_hash = expected_hashes.get(rel_path)
        if not exp_hash:
            violations.append(f"UNTRACKED_IN_MANIFEST: {rel_path}")
        elif curr_hash != exp_hash:
            violations.append(
                f"TAMPERED: {rel_path} (current={curr_hash[:12]} vs expected={exp_hash[:12]})"
            )

    return len(violations) == 0, violations
