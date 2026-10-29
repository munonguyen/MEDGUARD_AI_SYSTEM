from __future__ import annotations

from datetime import datetime, timezone

from app.services.external_evidence_registry import (
    evaluate_external_evidence_registry,
    registry_digest,
)


NOW = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
SHA = "a" * 64


def _registry(records: list[dict]) -> dict:
    payload = {
        "schema_version": "1.0.0",
        "status": "candidate",
        "records": records,
    }
    payload["registry_digest"] = registry_digest(payload)
    return payload


def _record(**overrides) -> dict:
    record = {
        "evidence_type": "database_backup_restore",
        "evidence_id": "backup-restore-2026-09-v1",
        "status": "approved",
        "artifact_sha256": SHA,
        "issued_at": "2026-09-20T00:00:00Z",
        "expires_at": "2026-10-20T00:00:00Z",
        "approved_by_ref": "ops-board-2026-09",
    }
    record.update(overrides)
    return record


def test_missing_required_evidence_fails_closed() -> None:
    result = evaluate_external_evidence_registry(
        _registry([]), now=NOW, required_types=("database_backup_restore",)
    )

    assert result["valid"] is False
    assert "missing:database_backup_restore" in result["blockers"]


def test_expired_evidence_is_rejected() -> None:
    result = evaluate_external_evidence_registry(
        _registry([_record(expires_at="2026-09-27T00:00:00Z")]),
        now=NOW,
        required_types=("database_backup_restore",),
    )

    assert result["valid"] is False
    assert any("expired" in blocker for blocker in result["blockers"])


def test_missing_or_invalid_artifact_checksum_is_rejected() -> None:
    result = evaluate_external_evidence_registry(
        _registry([_record(artifact_sha256="not-a-sha")]),
        now=NOW,
        required_types=("database_backup_restore",),
    )

    assert result["valid"] is False
    assert any("invalid_artifact_sha256" in blocker for blocker in result["blockers"])


def test_unapproved_evidence_is_rejected() -> None:
    result = evaluate_external_evidence_registry(
        _registry([_record(status="pending")]),
        now=NOW,
        required_types=("database_backup_restore",),
    )

    assert result["valid"] is False
    assert any("status=pending" in blocker for blocker in result["blockers"])


def test_current_approved_integrity_bound_evidence_passes() -> None:
    result = evaluate_external_evidence_registry(
        _registry([_record()]),
        now=NOW,
        required_types=("database_backup_restore",),
    )

    assert result["valid"] is True
    assert result["valid_types"] == ["database_backup_restore"]
    assert result["blockers"] == []


def test_registry_tampering_is_detected() -> None:
    payload = _registry([_record()])
    payload["records"][0]["evidence_id"] = "tampered"

    result = evaluate_external_evidence_registry(
        payload, now=NOW, required_types=("database_backup_restore",)
    )

    assert result["valid"] is False
    assert "registry_digest_mismatch" in result["blockers"]


def test_future_issued_evidence_is_rejected() -> None:
    result = evaluate_external_evidence_registry(
        _registry([_record(issued_at="2026-10-01T00:00:00Z")]),
        now=NOW,
        required_types=("database_backup_restore",),
    )

    assert result["valid"] is False
    assert any("issued_in_future" in blocker for blocker in result["blockers"])
