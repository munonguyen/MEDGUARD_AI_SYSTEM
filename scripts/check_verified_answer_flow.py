"""Probe the public MedGuard contract for an independently verified answer."""

from __future__ import annotations

import argparse
import json
from uuid import uuid4

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the provider-neutral answer-agent release contract."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--tenant-id", default="tenant-demo")
    parser.add_argument("--api-key", default="demo-key")
    parser.add_argument("--timeout", type=float, default=120.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    suffix = uuid4().hex
    try:
        response = httpx.post(
            f"{args.base_url.rstrip('/')}/v1/chat",
            headers={
                "X-Tenant-Id": args.tenant_id,
                "X-API-Key": args.api_key,
                "X-Consent-Token": "deidentified-agent-flow-probe",
                "Idempotency-Key": f"verified-answer-probe-{suffix}",
            },
            json={
                "conversation_id": f"verified-answer-probe-{suffix}",
                "messages": [
                    {
                        "role": "user",
                        "content": "Tôi đau đầu nhẹ từ sáng, không sốt, không yếu liệt và không khó thở.",
                    }
                ],
                "locale": "vi-VN",
            },
            timeout=args.timeout,
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        print(json.dumps({"verified": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    answer = body.get("answer") or {}
    assurance = answer.get("answer_assurance") or {}
    sources = answer.get("researched_sources") or []
    verified = assurance.get("status") == "verified" and bool(sources)
    print(
        json.dumps(
            {
                "verified": verified,
                "request_status": body.get("status"),
                "intent": body.get("intent"),
                "assurance_status": assurance.get("status"),
                "released_source_count": len(sources),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
