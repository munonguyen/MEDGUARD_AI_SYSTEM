from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_BENCHMARK = _ROOT / "datasets" / "DS-MEDICAL-RESPONSE-QUALITY" / "dataset.json"


def load_medical_response_benchmark_metadata(path: Path | None = None) -> dict[str, Any]:
    """Load only governance metadata from the medical-response benchmark.

    The evaluation set is useful as an engineering regression gate before it is
    clinician approved, but it must never silently become clinical validation.
    This helper centralizes that boundary for readiness and release tooling.
    """
    target = path or _DEFAULT_BENCHMARK
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    metadata = payload.get("_meta")
    return metadata if isinstance(metadata, dict) else {}


def clinical_validation_readiness(
    metadata: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Return production-readiness state for independent clinical review.

    Production requires all three explicit signals:
    - expert review status is approved;
    - the benchmark is marked production-evaluable;
    - a non-empty approval identifier/version is recorded.

    Engineering scores are intentionally ignored here. A high benchmark score
    cannot substitute for external clinician approval.
    """
    meta = metadata if metadata is not None else load_medical_response_benchmark_metadata()
    if not meta:
        return "fail", "medical-response benchmark metadata is missing or unreadable"

    review_status = str(meta.get("expert_review_status") or "").strip().lower()
    production_evaluable = meta.get("production_evaluable") is True
    approval_id = str(
        meta.get("clinical_approval_id")
        or meta.get("approval_id")
        or meta.get("clinical_review_version")
        or ""
    ).strip()

    blockers: list[str] = []
    if review_status != "approved":
        blockers.append(f"expert_review_status={review_status or 'missing'}")
    if not production_evaluable:
        blockers.append("production_evaluable=false")
    if not approval_id:
        blockers.append("clinical approval identifier/version is missing")

    if blockers:
        return (
            "fail",
            "independent clinical validation is not approved: " + "; ".join(blockers),
        )

    return (
        "pass",
        f"independent clinical validation approved; approval={approval_id}",
    )
