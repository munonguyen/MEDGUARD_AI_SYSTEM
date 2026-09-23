"""Freeze Guard and Manifest Generator for MedGuard AI Candidate V9.

Computes and verifies cryptographic SHA-256 hashes across all 5 core architecture groups:
A. Clinical Core
B. Tri-Gate
C. Knowledge
D. Calibration / Configuration
E. Evaluation-Critical Dependencies
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# Group A: Clinical Core
GROUP_A_CLINICAL_CORE: tuple[str, ...] = (
    "app/services/clinical_fact_parser.py",
    "app/services/semantic_relation_extractor.py",
    "app/services/semantic_abstraction_lattice.py",
    "app/services/evidence_strength_scorer.py",
    "app/services/clinical_threat_graph.py",
    "app/services/toxicology_reasoner.py",
    "app/services/toxicology_signature_router.py",
    "app/services/clinical_event_ledger.py",
    "app/services/physiologic_consequence_engine.py",
)

# Group B: Tri-Gate
GROUP_B_TRI_GATE: tuple[str, ...] = (
    "app/services/rules.py",
    "app/services/semantic_risk.py",
    "app/services/compositional_reasoner.py",
    "app/services/jev_engine.py",
    "app/services/jev_governance.py",
    "app/services/tri_gate_orchestrator.py",
    "app/services/tri_gate_resolver.py",
    "app/services/triage.py",
    "app/services/triage_resolver.py",
    "app/services/chat.py",
    "app/services/ood_guard.py",
)

# Group C: Knowledge
GROUP_C_KNOWLEDGE: tuple[str, ...] = (
    "app/knowledge/red_flag_protocols.json",
    "app/knowledge/medication_incident_protocols.json",
)

# Group D: Calibration / Configuration
GROUP_D_CALIBRATION_CONFIG: tuple[str, ...] = (
    "app/core/config.py",
    "app/models/jev.py",
    "app/models/clinical_events.py",
    "app/models/physiologic_consequences.py",
)

# Group E: Evaluation-Critical Dependencies
GROUP_E_EVAL_DEPENDENCIES: tuple[str, ...] = (
    "app/services/clinical_text.py",
    "scripts/run_900_regression.py",
)

REGRESSION_REPORT_PATH = "outputs/historical_regression_2100_report.json"


def compute_file_sha256(rel_path: str) -> str:
    p = REPO_ROOT / rel_path
    if not p.exists():
        raise FileNotFoundError(f"Missing required freeze file: {rel_path}")
    h = sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_group_hash(files: tuple[str, ...]) -> tuple[dict[str, str], str]:
    file_hashes: dict[str, str] = {}
    combined = sha256()
    for f in sorted(files):
        h = compute_file_sha256(f)
        file_hashes[f] = h
        combined.update(f"{f}:{h}".encode("utf-8"))
    return file_hashes, combined.hexdigest()


def get_git_commit() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_COMMIT"


def generate_freeze_manifest() -> dict[str, Any]:
    commit = get_git_commit()

    hashes_a, hash_group_a = compute_group_hash(GROUP_A_CLINICAL_CORE)
    hashes_b, hash_group_b = compute_group_hash(GROUP_B_TRI_GATE)
    hashes_c, hash_group_c = compute_group_hash(GROUP_C_KNOWLEDGE)
    hashes_d, hash_group_d = compute_group_hash(GROUP_D_CALIBRATION_CONFIG)
    hashes_e, hash_group_e = compute_group_hash(GROUP_E_EVAL_DEPENDENCIES)

    # Combined core manifest hash (Group A + Group B)
    core_combined = sha256(f"{hash_group_a}:{hash_group_b}".encode("utf-8")).hexdigest()
    regression_hash = compute_file_sha256(REGRESSION_REPORT_PATH)

    manifest = {
        "candidate": "MedGuard-V9",
        "git_commit": commit,
        "core_manifest_sha256": core_combined,
        "knowledge_sha256": hash_group_c,
        "config_sha256": hash_group_d,
        "model_config_sha256": hash_group_e,
        "regression_report_sha256": regression_hash,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "status": "FROZEN",
        "known_limitations": {
            "v1_specificity_pct": 75.86,
            "v7_specificity_pct": 87.37,
            "overall_specificity_pct": 95.56,
            "note": "Documented historical subgroup specificity gaps; candidate passed global 95.0% gate."
        },
        "component_group_hashes": {
            "group_a_clinical_core": hash_group_a,
            "group_b_tri_gate": hash_group_b,
            "group_c_knowledge": hash_group_c,
            "group_d_calibration_config": hash_group_d,
            "group_e_eval_dependencies": hash_group_e,
        },
        "file_hashes": {
            **hashes_a,
            **hashes_b,
            **hashes_c,
            **hashes_d,
            **hashes_e,
        },
    }

    out_file = REPO_ROOT / "blind_v9" / "freeze_manifest.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def verify_freeze_integrity(manifest_path: Path | None = None) -> tuple[bool, list[str]]:
    p = manifest_path or (REPO_ROOT / "blind_v9" / "freeze_manifest.json")
    if not p.exists():
        return False, [f"Manifest not found: {p}"]

    with open(p, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    errors: list[str] = []
    file_hashes = manifest.get("file_hashes", {})

    for rel_path, expected_h in file_hashes.items():
        try:
            actual_h = compute_file_sha256(rel_path)
            if actual_h != expected_h:
                errors.append(f"Tamper detected in {rel_path}: actual {actual_h[:8]} != expected {expected_h[:8]}")
        except FileNotFoundError:
            errors.append(f"Missing frozen file: {rel_path}")

    return (len(errors) == 0), errors


if __name__ == "__main__":
    m = generate_freeze_manifest()
    print("=" * 75)
    print("MEDGUARD AI CANDIDATE V9 — FREEZE MANIFEST GENERATED")
    print("=" * 75)
    print(f"Candidate:              {m['candidate']}")
    print(f"Git Commit:             {m['git_commit']}")
    print(f"Core Manifest SHA256:   {m['core_manifest_sha256']}")
    print(f"Knowledge SHA256:       {m['knowledge_sha256']}")
    print(f"Config SHA256:          {m['config_sha256']}")
    print(f"Model Config SHA256:    {m['model_config_sha256']}")
    print(f"Regression SHA256:      {m['regression_report_sha256']}")
    print(f"Status:                 {m['status']}")
    print(f"Saved to:               {REPO_ROOT / 'blind_v9' / 'freeze_manifest.json'}")
    print("=" * 75)
