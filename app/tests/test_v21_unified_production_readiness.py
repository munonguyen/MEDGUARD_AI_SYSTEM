from __future__ import annotations

from app.models.health import ReadinessCheck, ReadinessResponse


def test_readiness_response_appends_external_evidence_gate(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.external_evidence_registry.external_evidence_readiness",
        lambda: ("fail", "external production evidence incomplete; blockers=3"),
    )

    response = ReadinessResponse(
        status="ready",
        service="medguard-ai",
        environment="production",
        production_ready=True,
        checks=[
            ReadinessCheck(
                name="database",
                status="pass",
                detail="database healthy",
                required_for_production=True,
            )
        ],
    )

    checks = {check.name: check for check in response.checks}
    assert checks["external_production_evidence"].status == "fail"
    assert checks["external_production_evidence"].required_for_production is True
    assert response.production_ready is False
    assert response.status == "degraded"


def test_readiness_response_can_be_ready_only_when_external_evidence_passes(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.external_evidence_registry.external_evidence_readiness",
        lambda: ("pass", "all required external evidence is current"),
    )

    response = ReadinessResponse(
        status="degraded",
        service="medguard-ai",
        environment="production",
        production_ready=False,
        checks=[
            ReadinessCheck(
                name="database",
                status="pass",
                detail="database healthy",
                required_for_production=True,
            ),
            ReadinessCheck(
                name="independent_clinical_validation",
                status="pass",
                detail="approved",
                required_for_production=True,
            ),
        ],
    )

    assert response.production_ready is True
    assert response.status == "ready"
    assert sum(check.name == "external_production_evidence" for check in response.checks) == 1


def test_existing_external_evidence_check_is_not_duplicated(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.external_evidence_registry.external_evidence_readiness",
        lambda: ("fail", "should not be called for existing check"),
    )

    response = ReadinessResponse(
        status="ready",
        service="medguard-ai",
        environment="production",
        production_ready=True,
        checks=[
            ReadinessCheck(
                name="external_production_evidence",
                status="pass",
                detail="precomputed",
                required_for_production=True,
            )
        ],
    )

    assert response.production_ready is True
    assert response.status == "ready"
    assert sum(check.name == "external_production_evidence" for check in response.checks) == 1
