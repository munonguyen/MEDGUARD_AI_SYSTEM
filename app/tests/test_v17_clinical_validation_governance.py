from __future__ import annotations

from app.services.clinical_validation_governance import clinical_validation_readiness
from app.services.readiness import build_readiness


def test_pending_engineering_benchmark_is_not_clinical_validation() -> None:
    status, detail = clinical_validation_readiness(
        {
            "expert_review_status": "pending",
            "production_evaluable": False,
            "clinical_approval_id": "",
        }
    )

    assert status == "fail"
    assert "expert_review_status=pending" in detail
    assert "production_evaluable=false" in detail


def test_score_alone_cannot_override_missing_clinician_approval() -> None:
    # Scores are deliberately irrelevant to this gate. Even a perfect software
    # benchmark does not create independent clinical validation.
    status, _ = clinical_validation_readiness(
        {
            "expert_review_status": "pending",
            "production_evaluable": False,
            "average_score": 14.0,
            "critical_failures": 0,
        }
    )

    assert status == "fail"


def test_approved_production_evaluable_benchmark_requires_approval_identifier() -> None:
    status, detail = clinical_validation_readiness(
        {
            "expert_review_status": "approved",
            "production_evaluable": True,
        }
    )

    assert status == "fail"
    assert "approval identifier" in detail


def test_versioned_clinician_approval_passes_governance_gate() -> None:
    status, detail = clinical_validation_readiness(
        {
            "expert_review_status": "approved",
            "production_evaluable": True,
            "clinical_approval_id": "clinical-board-2026-09-v1",
        }
    )

    assert status == "pass"
    assert "clinical-board-2026-09-v1" in detail


def test_missing_metadata_fails_closed() -> None:
    status, detail = clinical_validation_readiness({})

    assert status == "fail"
    assert "missing or unreadable" in detail


def test_public_readiness_exposes_independent_clinical_validation_blocker() -> None:
    readiness = build_readiness()
    checks = {check.name: check for check in readiness.checks}

    assert "independent_clinical_validation" in checks
    check = checks["independent_clinical_validation"]
    assert check.required_for_production is True
    # The repository benchmark is intentionally pending clinician review today.
    assert check.status == "fail"
    assert readiness.production_ready is False
