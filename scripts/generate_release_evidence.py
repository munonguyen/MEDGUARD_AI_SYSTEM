"""Generate a machine-readable MedGuard release evidence manifest.

The manifest records engineering evidence and external approval state without
serializing secrets. It is evidence *about* a candidate release, not a clinical
approval mechanism: missing external approvals remain explicit blockers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings
from app.services.adaptive_agent_runtime import adaptive_agent_runtime
from app.services.clinical_validation_governance import (
    clinical_validation_readiness,
    load_medical_response_benchmark_metadata,
)
from app.services.external_evidence_registry import evaluate_external_evidence_registry
from app.services.readiness import build_readiness
from scripts.benchmark_professional_response import run_professional_response_benchmark
from scripts.evaluate_medical_response_quality import run_benchmark as run_medical_response_quality_benchmark


SCHEMA_VERSION = "1.1.0"


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def evidence_digest(payload: dict[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("evidence_digest", None)
    return hashlib.sha256(_canonical_json(unsigned)).hexdigest()


def _safe_model_configuration() -> dict[str, Any]:
    runtime = adaptive_agent_runtime
    return {
        "agent_mode": settings.agent_mode,
        "coverage_scope": settings.agent_coverage_scope,
        "research_model_alias": settings.research_agent_model,
        "verifier_model_alias": settings.verifier_agent_model,
        "clinical_writer_alias": getattr(settings, "clinical_research_model", None),
        "clinical_verifier_alias": getattr(settings, "clinical_verifier_model", None),
        "pharma_writer_alias": getattr(settings, "pharma_research_model", None),
        "pharma_verifier_alias": getattr(settings, "pharma_verifier_model", None),
        "prompt_version": settings.agent_prompt_version,
        "adaptive_routing": {
            "requested_mode": runtime.config.mode,
            "effective_mode": runtime.mode,
            "kev_model": runtime.config.kev_model,
            "kev_endpoint_configured": bool(runtime.config.kev_base_url),
            "kev_calibration_status": runtime.config.kev_calibration_status,
            "kev_calibration_version": runtime.config.kev_calibration_version,
        },
    }


def _readiness_payload(readiness: Any) -> dict[str, Any]:
    checks = []
    blockers = []
    for check in readiness.checks:
        item = {
            "name": check.name,
            "status": check.status,
            "required_for_production": check.required_for_production,
            "detail": check.detail,
        }
        checks.append(item)
        if check.required_for_production and check.status != "pass":
            blockers.append(check.name)
    return {
        "status": readiness.status,
        "production_ready": readiness.production_ready,
        "checks": checks,
        "required_blockers": blockers,
    }


def build_release_evidence(
    *,
    readiness: Any | None = None,
    medical_quality: dict[str, Any] | None = None,
    professional_quality: dict[str, Any] | None = None,
    clinical_metadata: dict[str, Any] | None = None,
    external_evidence: dict[str, Any] | None = None,
    git_sha: str | None = None,
    generated_at: str | None = None,
    model_configuration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    readiness_obj = readiness or build_readiness()
    medical = medical_quality or run_medical_response_quality_benchmark()
    professional = professional_quality or run_professional_response_benchmark()
    clinical_meta = (
        clinical_metadata
        if clinical_metadata is not None
        else load_medical_response_benchmark_metadata()
    )
    clinical_status, clinical_detail = clinical_validation_readiness(clinical_meta)
    external = external_evidence or evaluate_external_evidence_registry()
    readiness_data = _readiness_payload(readiness_obj)

    medical_summary = {
        "dataset_version": medical.get("dataset_version"),
        "expert_review_status": medical.get("expert_review_status"),
        "production_evaluable": medical.get("production_evaluable"),
        "total": medical.get("total"),
        "average_score": medical.get("average_score"),
        "critical_failures": medical.get("critical_failures"),
        "subthreshold_cases": medical.get("subthreshold_cases"),
        "p95_latency_ms": medical.get("p95_latency_ms"),
        "gate_passed": bool(medical.get("gate_passed")),
    }
    professional_summary = {
        "total": professional.get("total"),
        "correct": professional.get("correct"),
        "average_good_score": professional.get("average_good_score"),
        "critical_failures": professional.get("critical_failures"),
        "false_accepts": professional.get("false_accepts"),
        "false_rejects": professional.get("false_rejects"),
        "gate_passed": bool(professional.get("gate_passed")),
    }
    external_summary = {
        "status": external.get("status"),
        "valid": bool(external.get("valid")),
        "required_types": list(external.get("required_types") or []),
        "valid_types": list(external.get("valid_types") or []),
        "blockers": list(external.get("blockers") or []),
        "detail": external.get("detail"),
    }

    blockers = list(readiness_data["required_blockers"])
    if not medical_summary["gate_passed"]:
        blockers.append("medical_response_quality")
    if not professional_summary["gate_passed"]:
        blockers.append("professional_response_quality")
    if clinical_status != "pass" and "independent_clinical_validation" not in blockers:
        blockers.append("independent_clinical_validation")
    if not external_summary["valid"]:
        blockers.append("external_production_evidence")

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "code_sha": git_sha or _git_sha(),
        "environment": settings.environment,
        "service": settings.service_name,
        "readiness": readiness_data,
        "quality": {
            "medical_response": medical_summary,
            "professional_response": professional_summary,
        },
        "clinical_validation": {
            "status": clinical_status,
            "detail": clinical_detail,
            "expert_review_status": clinical_meta.get("expert_review_status"),
            "production_evaluable": clinical_meta.get("production_evaluable"),
            "clinical_approval_id": (
                clinical_meta.get("clinical_approval_id")
                or clinical_meta.get("approval_id")
                or clinical_meta.get("clinical_review_version")
            ),
        },
        "external_production_evidence": external_summary,
        "model_configuration": model_configuration or _safe_model_configuration(),
        "production_release_eligible": (
            bool(readiness_data["production_ready"])
            and medical_summary["gate_passed"]
            and professional_summary["gate_passed"]
            and clinical_status == "pass"
            and external_summary["valid"]
        ),
        "release_blockers": sorted(set(blockers)),
        "governance_note": (
            "This manifest records engineering evidence and approval state; "
            "it cannot create or substitute for independent clinical or operational approval."
        ),
    }
    payload["evidence_digest"] = evidence_digest(payload)
    return payload


def validate_release_evidence(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported_schema_version")
    if not payload.get("code_sha"):
        errors.append("missing_code_sha")
    expected_digest = evidence_digest(payload)
    if payload.get("evidence_digest") != expected_digest:
        errors.append("evidence_digest_mismatch")

    eligible = bool(payload.get("production_release_eligible"))
    blockers = payload.get("release_blockers") or []
    if eligible and blockers:
        errors.append("eligible_release_has_blockers")
    if eligible:
        readiness = payload.get("readiness") or {}
        quality = payload.get("quality") or {}
        clinical = payload.get("clinical_validation") or {}
        external = payload.get("external_production_evidence") or {}
        if readiness.get("production_ready") is not True:
            errors.append("eligible_without_production_readiness")
        if (quality.get("medical_response") or {}).get("gate_passed") is not True:
            errors.append("eligible_without_medical_quality")
        if (quality.get("professional_response") or {}).get("gate_passed") is not True:
            errors.append("eligible_without_professional_quality")
        if clinical.get("status") != "pass":
            errors.append("eligible_without_clinical_validation")
        if external.get("valid") is not True:
            errors.append("eligible_without_external_evidence")
    return not errors, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=BASE_DIR / "release_evidence.json",
        help="Path for the generated evidence manifest.",
    )
    parser.add_argument(
        "--require-production-eligible",
        action="store_true",
        help="Exit non-zero unless all production evidence and approvals are present.",
    )
    args = parser.parse_args()

    payload = build_release_evidence()
    valid, errors = validate_release_evidence(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"release_evidence={'VALID' if valid else 'INVALID'} "
        f"production_release_eligible={str(payload['production_release_eligible']).lower()} "
        f"blockers={','.join(payload['release_blockers']) or 'none'} "
        f"digest={payload['evidence_digest']}"
    )
    if not valid:
        print("validation_errors=" + ",".join(errors))
        return 2
    if args.require_production_eligible and not payload["production_release_eligible"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
