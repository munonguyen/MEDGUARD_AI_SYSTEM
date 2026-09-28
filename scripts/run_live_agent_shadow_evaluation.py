"""Run deidentified evaluation-only cases through a deployed MedGuard chat API.

This harness records model-path behavior and safety signals without storing API
keys or treating machine results as clinical approval. It is intentionally not
part of hermetic CI because a real deployed gateway is required.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.services.shadow_evaluation import evaluate_shadow_cases, validate_shadow_report


DEFAULT_DATASET = BASE_DIR / "datasets" / "DS-MEDICAL-RESPONSE-QUALITY" / "dataset.json"


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _load_dataset(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else {}
    cases = payload.get("cases") if isinstance(payload.get("cases"), list) else []
    if not cases:
        raise ValueError("shadow dataset contains no cases")
    if meta.get("training_allowed") is not False:
        raise ValueError("shadow evaluation dataset must explicitly set training_allowed=false")
    source_kind = str(meta.get("source_kind") or "").lower()
    if "synthetic" not in source_kind and "deident" not in source_kind:
        raise ValueError("shadow evaluation requires synthetic or deidentified source_kind")
    return meta, cases


def _observation_from_response(
    case: dict[str, Any], response: dict[str, Any], *, latency_ms: float
) -> dict[str, Any]:
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    answer = response.get("answer") if isinstance(response.get("answer"), dict) else {}
    researched_sources = answer.get("researched_sources") if isinstance(answer.get("researched_sources"), list) else []
    urgency = result.get("urgency") or result.get("risk")
    return {
        "case_id": case.get("case_id"),
        "expected": case.get("expected") or {},
        "intent": response.get("intent"),
        "urgency": urgency,
        "answer_origin": response.get("answer_origin"),
        "verification_status": response.get("verification_status"),
        "citation_count": len(researched_sources),
        "latency_ms": round(latency_ms, 2),
        "reply": response.get("reply") or "",
        "request_id": response.get("request_id"),
    }


def run_live_shadow(
    *,
    base_url: str,
    api_key: str,
    tenant_id: str,
    consent_token: str,
    cases: list[dict[str, Any]],
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_seconds) as client:
        for index, case in enumerate(cases, start=1):
            case_id = str(case.get("case_id") or f"case-{index}")
            prompt = str(case.get("prompt") or "").strip()
            if not prompt:
                raise ValueError(f"{case_id} has an empty prompt")
            headers = {
                "X-API-Key": api_key,
                "X-Tenant-Id": tenant_id,
                "X-Consent-Token": consent_token,
                "Idempotency-Key": f"shadow-{case_id}-{index}",
            }
            body = {
                "conversation_id": f"shadow-eval-{case_id}-{index}",
                "messages": [{"role": "user", "content": prompt}],
                "intent_hint": "auto",
                "locale": "vi-VN",
            }
            started = time.perf_counter()
            response = client.post("/v1/chat", headers=headers, json=body)
            latency_ms = (time.perf_counter() - started) * 1000.0
            response.raise_for_status()
            observations.append(
                _observation_from_response(case, response.json(), latency_ms=latency_ms)
            )
    return observations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("MEDGUARD_SHADOW_BASE_URL"))
    parser.add_argument("--api-key", default=os.getenv("MEDGUARD_SHADOW_API_KEY"))
    parser.add_argument("--tenant-id", default=os.getenv("MEDGUARD_SHADOW_TENANT_ID", "shadow-eval"))
    parser.add_argument("--consent-token", default=os.getenv("MEDGUARD_SHADOW_CONSENT_TOKEN"))
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=BASE_DIR / "live_shadow_report.json")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--writer-alias", default=os.getenv("MEDGUARD_RESEARCH_AGENT_MODEL"))
    parser.add_argument("--reviewer-alias", default=os.getenv("MEDGUARD_VERIFIER_AGENT_MODEL"))
    args = parser.parse_args()

    if not args.base_url or not args.api_key or not args.consent_token:
        parser.error(
            "a deployed base URL, API key and consent token are required; "
            "the harness will not fabricate live evidence"
        )
    if args.timeout_seconds <= 0:
        parser.error("timeout-seconds must be positive")

    meta, cases = _load_dataset(args.dataset)
    if args.limit > 0:
        cases = cases[: args.limit]
    observations = run_live_shadow(
        base_url=args.base_url,
        api_key=args.api_key,
        tenant_id=args.tenant_id,
        consent_token=args.consent_token,
        cases=cases,
        timeout_seconds=args.timeout_seconds,
    )
    report = evaluate_shadow_cases(
        observations,
        dataset_meta=meta,
        code_sha=_git_sha(),
        writer_alias=args.writer_alias,
        reviewer_alias=args.reviewer_alias,
    )
    valid, errors = validate_shadow_report(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"live_shadow_report={'VALID' if valid else 'INVALID'} "
        f"machine_gate={'PASS' if report['gate_passed'] else 'FAIL'} "
        f"verified={report['gateway_verified']}/{report['total']} "
        f"fallbacks={report['deterministic_fallbacks']} "
        f"p95={report['p95_latency_ms']}ms"
    )
    if not valid:
        print("validation_errors=" + ",".join(errors))
        return 2
    return 0 if report["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
