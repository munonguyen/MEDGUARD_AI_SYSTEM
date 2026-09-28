from __future__ import annotations

from types import SimpleNamespace

from scripts.generate_release_evidence import (
    build_release_evidence,
    validate_release_evidence,
)


def _readiness(*, production_ready: bool, failed_required: tuple[str, ...] = ()) -> SimpleNamespace:
    names = ("database", "independent_clinical_validation")
    checks = [
        SimpleNamespace(
            name=name,
            status="fail" if name in failed_required else "pass",
            required_for_production=True,
            detail=f"{name} detail",
        )
        for name in names
    ]
    return SimpleNamespace(
        status="ready" if production_ready else "degraded",
        production_ready=production_ready,
        checks=checks,
    )


def _medical(*, passed: bool = True) -> dict:
    return {
        "dataset_version": "1.0.0",
        "expert_review_status": "pending",
        "production_evaluable": False,
        "total": 40,
        "average_score": 12.6,
        "critical_failures": 0 if passed else 1,
        "subthreshold_cases": 0,
        "p95_latency_ms": 700.0,
        "gate_passed": passed,
    }


def _professional(*, passed: bool = True) -> dict:
    return {
        "total": 12,
        "correct": 12 if passed else 11,
        "average_good_score": 0.99,
        "critical_failures": [] if passed else ["bad-emergency"],
        "false_accepts": [],
        "false_rejects": [],
        "gate_passed": passed,
    }


def _external(*, valid: bool = True) -> dict:
    return {
        "status": "pass" if valid else "fail",
        "valid": valid,
        "required_types": ["database_backup_restore"],
        "valid_types": ["database_backup_restore"] if valid else [],
        "blockers": [] if valid else ["missing:database_backup_restore"],
        "detail": "external evidence complete" if valid else "external evidence incomplete",
    }


def _models() -> dict:
    return {
        "agent_mode": "enforced",
        "research_model_alias": "writer-alias",
        "verifier_model_alias": "reviewer-alias",
        "adaptive_routing": {
            "requested_mode": "shadow",
            "effective_mode": "shadow",
            "kev_model": "kev-latest",
            "kev_endpoint_configured": False,
            "kev_calibration_status": "unvalidated",
            "kev_calibration_version": None,
        },
    }


def test_pending_clinician_review_is_explicit_release_blocker() -> None:
    payload = build_release_evidence(
        readiness=_readiness(
            production_ready=False,
            failed_required=("independent_clinical_validation",),
        ),
        medical_quality=_medical(),
        professional_quality=_professional(),
        clinical_metadata={
            "expert_review_status": "pending",
            "production_evaluable": False,
        },
        external_evidence=_external(),
        git_sha="abc123",
        generated_at="2026-09-28T00:00:00+00:00",
        model_configuration=_models(),
    )

    assert payload["production_release_eligible"] is False
    assert "independent_clinical_validation" in payload["release_blockers"]
    valid, errors = validate_release_evidence(payload)
    assert valid is True
    assert errors == []


def test_fully_approved_evidence_can_be_release_eligible() -> None:
    payload = build_release_evidence(
        readiness=_readiness(production_ready=True),
        medical_quality=_medical(),
        professional_quality=_professional(),
        clinical_metadata={
            "expert_review_status": "approved",
            "production_evaluable": True,
            "clinical_approval_id": "board-v1",
        },
        external_evidence=_external(),
        git_sha="abc123",
        generated_at="2026-09-28T00:00:00+00:00",
        model_configuration=_models(),
    )

    assert payload["production_release_eligible"] is True
    assert payload["release_blockers"] == []
    valid, errors = validate_release_evidence(payload)
    assert valid is True
    assert errors == []


def test_external_evidence_is_required_for_release_eligibility() -> None:
    payload = build_release_evidence(
        readiness=_readiness(production_ready=True),
        medical_quality=_medical(),
        professional_quality=_professional(),
        clinical_metadata={
            "expert_review_status": "approved",
            "production_evaluable": True,
            "clinical_approval_id": "board-v1",
        },
        external_evidence=_external(valid=False),
        git_sha="abc123",
        generated_at="2026-09-28T00:00:00+00:00",
        model_configuration=_models(),
    )

    assert payload["production_release_eligible"] is False
    assert "external_production_evidence" in payload["release_blockers"]
    assert payload["external_production_evidence"]["valid"] is False


def test_failed_quality_gate_is_recorded_as_blocker() -> None:
    payload = build_release_evidence(
        readiness=_readiness(production_ready=True),
        medical_quality=_medical(passed=False),
        professional_quality=_professional(),
        clinical_metadata={
            "expert_review_status": "approved",
            "production_evaluable": True,
            "clinical_approval_id": "board-v1",
        },
        external_evidence=_external(),
        git_sha="abc123",
        generated_at="2026-09-28T00:00:00+00:00",
        model_configuration=_models(),
    )

    assert payload["production_release_eligible"] is False
    assert "medical_response_quality" in payload["release_blockers"]


def test_digest_detects_manifest_tampering() -> None:
    payload = build_release_evidence(
        readiness=_readiness(production_ready=True),
        medical_quality=_medical(),
        professional_quality=_professional(),
        clinical_metadata={
            "expert_review_status": "approved",
            "production_evaluable": True,
            "clinical_approval_id": "board-v1",
        },
        external_evidence=_external(),
        git_sha="abc123",
        generated_at="2026-09-28T00:00:00+00:00",
        model_configuration=_models(),
    )
    payload["code_sha"] = "tampered"

    valid, errors = validate_release_evidence(payload)
    assert valid is False
    assert "evidence_digest_mismatch" in errors


def test_validator_rejects_eligible_manifest_without_external_evidence() -> None:
    payload = build_release_evidence(
        readiness=_readiness(production_ready=True),
        medical_quality=_medical(),
        professional_quality=_professional(),
        clinical_metadata={
            "expert_review_status": "approved",
            "production_evaluable": True,
            "clinical_approval_id": "board-v1",
        },
        external_evidence=_external(),
        git_sha="abc123",
        generated_at="2026-09-28T00:00:00+00:00",
        model_configuration=_models(),
    )
    payload["external_production_evidence"]["valid"] = False
    payload["evidence_digest"] = __import__("scripts.generate_release_evidence", fromlist=["evidence_digest"]).evidence_digest(payload)

    valid, errors = validate_release_evidence(payload)
    assert valid is False
    assert "eligible_without_external_evidence" in errors


def test_manifest_does_not_need_or_store_secret_values() -> None:
    payload = build_release_evidence(
        readiness=_readiness(production_ready=False, failed_required=("database",)),
        medical_quality=_medical(),
        professional_quality=_professional(),
        clinical_metadata={
            "expert_review_status": "pending",
            "production_evaluable": False,
        },
        external_evidence=_external(valid=False),
        git_sha="abc123",
        generated_at="2026-09-28T00:00:00+00:00",
        model_configuration=_models(),
    )
    serialized = str(payload).lower()

    assert "api_key" not in serialized
    assert "master_key" not in serialized
    assert "delivery_hmac_secret" not in serialized
