from __future__ import annotations

from types import SimpleNamespace

from scripts.generate_release_evidence import build_release_evidence, evidence_digest
from scripts.verify_production_promotion import verify_production_promotion


def _readiness(*, ready: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        status="ready" if ready else "degraded",
        production_ready=ready,
        checks=[
            SimpleNamespace(
                name="runtime",
                status="pass" if ready else "fail",
                required_for_production=True,
                detail="runtime gate",
            )
        ],
    )


def _medical(*, passed: bool = True) -> dict:
    return {
        "dataset_version": "1.0.0",
        "expert_review_status": "approved",
        "production_evaluable": True,
        "total": 40,
        "average_score": 13.0,
        "critical_failures": 0 if passed else 1,
        "subthreshold_cases": 0,
        "p95_latency_ms": 500.0,
        "gate_passed": passed,
    }


def _professional(*, passed: bool = True) -> dict:
    return {
        "total": 12,
        "correct": 12 if passed else 11,
        "average_good_score": 1.0,
        "critical_failures": [] if passed else ["case"],
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
        "detail": "complete" if valid else "incomplete",
    }


def _models() -> dict:
    return {
        "agent_mode": "enforced",
        "coverage_scope": "all",
        "research_model_alias": "writer",
        "verifier_model_alias": "reviewer",
        "adaptive_routing": {
            "requested_mode": "disabled",
            "effective_mode": "disabled",
            "kev_model": "kev",
            "kev_endpoint_configured": False,
            "kev_calibration_status": "not_required",
            "kev_calibration_version": None,
        },
    }


def _eligible_payload(*, sha: str = "candidate123") -> dict:
    return build_release_evidence(
        readiness=_readiness(),
        medical_quality=_medical(),
        professional_quality=_professional(),
        clinical_metadata={
            "expert_review_status": "approved",
            "production_evaluable": True,
            "clinical_approval_id": "clinical-board-v1",
        },
        external_evidence=_external(),
        git_sha=sha,
        generated_at="2026-09-29T00:00:00+00:00",
        model_configuration=_models(),
    )


def test_fully_bound_candidate_is_allowed() -> None:
    payload = _eligible_payload()

    passed, errors = verify_production_promotion(payload, expected_code_sha="candidate123")

    assert passed is True
    assert errors == []


def test_candidate_sha_mismatch_blocks_promotion() -> None:
    payload = _eligible_payload()

    passed, errors = verify_production_promotion(payload, expected_code_sha="different")

    assert passed is False
    assert "candidate_code_sha_mismatch" in errors


def test_current_repository_state_cannot_self_authorize_with_blockers() -> None:
    payload = build_release_evidence(
        readiness=_readiness(ready=False),
        medical_quality=_medical(),
        professional_quality=_professional(),
        clinical_metadata={
            "expert_review_status": "pending",
            "production_evaluable": False,
        },
        external_evidence=_external(valid=False),
        git_sha="candidate123",
        generated_at="2026-09-29T00:00:00+00:00",
        model_configuration=_models(),
    )

    passed, errors = verify_production_promotion(payload, expected_code_sha="candidate123")

    assert passed is False
    assert "production_release_not_eligible" in errors
    assert "release_blockers_present" in errors
    assert "external_production_evidence_not_valid" in errors
    assert "independent_clinical_validation_not_passed" in errors
    assert "runtime_production_readiness_not_passed" in errors


def test_tampered_manifest_is_blocked_even_if_eligibility_stays_true() -> None:
    payload = _eligible_payload()
    payload["model_configuration"]["research_model_alias"] = "tampered-writer"

    passed, errors = verify_production_promotion(payload, expected_code_sha="candidate123")

    assert passed is False
    assert "manifest:evidence_digest_mismatch" in errors


def test_recomputed_digest_cannot_hide_false_external_evidence() -> None:
    payload = _eligible_payload()
    payload["external_production_evidence"]["valid"] = False
    payload["evidence_digest"] = evidence_digest(payload)

    passed, errors = verify_production_promotion(payload, expected_code_sha="candidate123")

    assert passed is False
    assert "external_production_evidence_not_valid" in errors
    assert "manifest:eligible_without_external_evidence" in errors


def test_quality_failure_blocks_even_if_flags_are_manually_flipped() -> None:
    payload = _eligible_payload()
    payload["quality"]["medical_response"]["gate_passed"] = False
    payload["production_release_eligible"] = True
    payload["release_blockers"] = []
    payload["evidence_digest"] = evidence_digest(payload)

    passed, errors = verify_production_promotion(payload, expected_code_sha="candidate123")

    assert passed is False
    assert "medical_response_quality_not_passed" in errors
    assert "manifest:eligible_without_medical_quality" in errors
