from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_REGISTRY = _ROOT / "governance" / "external_evidence_registry.json"

_REQUIRED_EVIDENCE_TYPES = (
    "database_backup_restore",
    "database_tenant_isolation",
    "redis_persistence_failover",
    "queue_dead_letter_alerting",
    "object_storage_lifecycle",
    "secret_rotation",
    "consent_system",
    "ocr_model_integrity",
    "multi_replica_rate_limit",
    "observability_slo",
    "security_testing",
    "disaster_recovery",
    "provider_data_controls",
    "live_agent_shadow_evaluation",
)


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def registry_digest(payload: dict[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("registry_digest", None)
    return hashlib.sha256(_canonical_json(unsigned)).hexdigest()


def load_external_evidence_registry(path: Path | None = None) -> dict[str, Any]:
    target = path or _DEFAULT_REGISTRY
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def evaluate_external_evidence_registry(
    payload: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
    required_types: tuple[str, ...] = _REQUIRED_EVIDENCE_TYPES,
) -> dict[str, Any]:
    """Evaluate external deployment evidence without fabricating missing proof.

    Evidence is accepted only when it is explicitly approved, has a version/id,
    binds to an artifact SHA-256, has valid issuance/expiry timestamps, and is
    not expired. Registry integrity is independently checked with SHA-256.
    """
    registry = payload if payload is not None else load_external_evidence_registry()
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    failures: list[str] = []
    valid_types: list[str] = []

    if not registry:
        return {
            "status": "fail",
            "valid": False,
            "required_types": list(required_types),
            "valid_types": [],
            "blockers": ["registry_missing_or_unreadable", *[f"missing:{item}" for item in required_types]],
            "detail": "external production evidence registry is missing or unreadable",
        }

    expected_digest = registry_digest(registry)
    if registry.get("registry_digest") != expected_digest:
        failures.append("registry_digest_mismatch")

    records = registry.get("records")
    if not isinstance(records, list):
        records = []
        failures.append("records_missing_or_invalid")

    by_type: dict[str, list[dict[str, Any]]] = {}
    for raw in records:
        if not isinstance(raw, dict):
            failures.append("invalid_record_shape")
            continue
        evidence_type = str(raw.get("evidence_type") or "").strip()
        if evidence_type:
            by_type.setdefault(evidence_type, []).append(raw)

    for evidence_type in required_types:
        candidates = by_type.get(evidence_type, [])
        if not candidates:
            failures.append(f"missing:{evidence_type}")
            continue

        accepted = False
        reasons: list[str] = []
        for record in candidates:
            status = str(record.get("status") or "").strip().lower()
            evidence_id = str(record.get("evidence_id") or record.get("version") or "").strip()
            artifact_sha256 = record.get("artifact_sha256")
            issued_at = _parse_time(record.get("issued_at"))
            expires_at = _parse_time(record.get("expires_at"))

            record_errors: list[str] = []
            if status != "approved":
                record_errors.append(f"status={status or 'missing'}")
            if not evidence_id:
                record_errors.append("missing_evidence_id")
            if not _is_sha256(artifact_sha256):
                record_errors.append("invalid_artifact_sha256")
            if issued_at is None:
                record_errors.append("invalid_issued_at")
            elif issued_at > current:
                record_errors.append("issued_in_future")
            if expires_at is None:
                record_errors.append("invalid_expires_at")
            elif expires_at <= current:
                record_errors.append("expired")
            if issued_at is not None and expires_at is not None and expires_at <= issued_at:
                record_errors.append("expiry_not_after_issue")

            if not record_errors:
                accepted = True
                break
            reasons.extend(record_errors)

        if accepted:
            valid_types.append(evidence_type)
        else:
            suffix = ",".join(sorted(set(reasons))) or "no_approved_current_record"
            failures.append(f"invalid:{evidence_type}:{suffix}")

    valid = not failures
    return {
        "status": "pass" if valid else "fail",
        "valid": valid,
        "required_types": list(required_types),
        "valid_types": valid_types,
        "blockers": failures,
        "detail": (
            "all required external production evidence is approved, current and integrity-bound"
            if valid
            else f"external production evidence incomplete; blockers={len(failures)}"
        ),
    }


def external_evidence_readiness() -> tuple[str, str]:
    result = evaluate_external_evidence_registry()
    return str(result["status"]), str(result["detail"])
