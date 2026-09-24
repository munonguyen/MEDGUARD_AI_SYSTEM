"""Cryptographic sealing helpers for the independent Blind V10 one-shot run."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
from typing import Any


HMAC_KEY_ENV = "MEDGUARD_BLIND_V10_HMAC_KEY"
CANARY_ENV = "MEDGUARD_BLIND_V10_CANARY"


def file_sha256(path: Path | str) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _key() -> bytes:
    value = os.environ.get(HMAC_KEY_ENV, "")
    if len(value) < 32:
        raise RuntimeError(
            f"{HMAC_KEY_ENV} must be provided by the independent evaluator "
            "and contain at least 32 characters"
        )
    return value.encode("utf-8")


def check_canary_leakage(path: Path | str) -> tuple[bool, str]:
    token = os.environ.get(CANARY_ENV, "")
    if len(token) < 16:
        return False, f"{CANARY_ENV} is missing or too short"
    content = Path(path).read_text(encoding="utf-8", errors="ignore")
    if token in content:
        return False, "oracle leakage canary found in predictions"
    return True, "oracle leakage canary absent from predictions"


def seal_predictions(
    predictions_path: Path | str,
    cases_path: Path | str,
    manifest_path: Path | str,
    *,
    candidate_commit: str,
) -> dict[str, Any]:
    predictions = Path(predictions_path)
    cases = Path(cases_path)
    prediction_hash = file_sha256(predictions)
    cases_hash = file_sha256(cases)
    entry_count = sum(1 for line in predictions.read_text(encoding="utf-8").splitlines() if line.strip())
    signed_payload = {
        "format": "medguard-blind-v10-predictions-seal-v1",
        "candidate_commit": candidate_commit,
        "cases_sha256": cases_hash,
        "predictions_sha256": prediction_hash,
        "entry_count": entry_count,
        "sealed_at": datetime.now(timezone.utc).isoformat(),
    }
    canonical = json.dumps(signed_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest = {
        **signed_payload,
        "hmac_sha256": hmac.new(_key(), canonical, sha256).hexdigest(),
    }
    target = Path(manifest_path)
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def verify_predictions_seal(
    predictions_path: Path | str,
    cases_path: Path | str,
    manifest_path: Path | str,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    predictions = Path(predictions_path)
    cases = Path(cases_path)
    manifest_file = Path(manifest_path)
    if not predictions.exists() or not cases.exists() or not manifest_file.exists():
        return False, ["predictions, cases, or seal manifest is missing"]
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    signature = str(manifest.pop("hmac_sha256", ""))
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected_signature = hmac.new(_key(), canonical, sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        errors.append("prediction seal HMAC mismatch")
    if manifest.get("predictions_sha256") != file_sha256(predictions):
        errors.append("predictions SHA-256 mismatch")
    if manifest.get("cases_sha256") != file_sha256(cases):
        errors.append("sealed cases SHA-256 mismatch")
    canary_ok, canary_message = check_canary_leakage(predictions)
    if not canary_ok:
        errors.append(canary_message)
    return not errors, errors
