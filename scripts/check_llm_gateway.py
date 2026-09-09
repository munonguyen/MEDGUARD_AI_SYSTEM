"""Check LiteLLM availability and optionally probe MedGuard model aliases."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import httpx


ALIASES = ("medguard-answer", "medguard-verifier")


def _gateway_root(value: str) -> str:
    return value.rstrip("/").removesuffix("/v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the MedGuard LLM gateway.")
    parser.add_argument(
        "--gateway-url",
        default=os.getenv(
            "MEDGUARD_LLM_GATEWAY_URL",
            os.getenv("LITELLM_GATEWAY_URL", "http://127.0.0.1:4000/v1"),
        ),
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("MEDGUARD_LLM_GATEWAY_API_KEY"),
    )
    parser.add_argument("--probe-models", action="store_true")
    parser.add_argument("--timeout", type=float, default=15.0)
    return parser.parse_args()


def _probe(client: httpx.Client, base_url: str, alias: str) -> dict[str, Any]:
    response = client.post(
        f"{base_url}/v1/responses",
        json={
            "model": alias,
            "input": "Return the single token OK. Do not process patient data.",
            "max_output_tokens": 16,
            "store": False,
            "cache": {"no-cache": True, "no-store": True},
        },
    )
    response.raise_for_status()
    body = response.json()
    return {
        "alias": alias,
        "ok": bool(body.get("id") or body.get("output") or body.get("output_text")),
    }


def main() -> int:
    args = parse_args()
    if not args.api_key:
        print("MEDGUARD_LLM_GATEWAY_API_KEY or --api-key is required", file=sys.stderr)
        return 2
    root = _gateway_root(args.gateway_url)
    headers = {"Authorization": f"Bearer {args.api_key}"}
    report: dict[str, Any] = {"gateway": root, "liveliness": False, "probes": []}
    try:
        with httpx.Client(headers=headers, timeout=args.timeout) as client:
            response = client.get(f"{root}/health/liveliness")
            response.raise_for_status()
            report["liveliness"] = True
            if args.probe_models:
                report["probes"] = [_probe(client, root, alias) for alias in ALIASES]
    except (httpx.HTTPError, ValueError) as exc:
        report["error"] = str(exc)
        print(json.dumps(report, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0 if all(item.get("ok") for item in report["probes"]) else int(args.probe_models)


if __name__ == "__main__":
    raise SystemExit(main())
