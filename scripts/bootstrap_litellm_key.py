"""Create a budgeted LiteLLM virtual key for the MedGuard backend."""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx


DEFAULT_MODELS = (
    "medguard-answer",
    "medguard-verifier",
)


def _gateway_root(value: str) -> str:
    return value.rstrip("/").removesuffix("/v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a role-scoped, budgeted LiteLLM virtual key."
    )
    parser.add_argument(
        "--gateway-url",
        default=os.getenv("LITELLM_GATEWAY_URL", "http://127.0.0.1:4000"),
    )
    parser.add_argument("--master-key", default=os.getenv("LITELLM_MASTER_KEY"))
    parser.add_argument("--team-id", default="medguard-backend")
    parser.add_argument("--max-budget", type=float, default=100.0)
    parser.add_argument("--budget-duration", default="30d")
    parser.add_argument("--duration", default="90d")
    parser.add_argument("--rpm-limit", type=int, default=120)
    parser.add_argument("--tpm-limit", type=int, default=500_000)
    parser.add_argument("--max-parallel-requests", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.master_key:
        print("LITELLM_MASTER_KEY or --master-key is required", file=sys.stderr)
        return 2
    payload = {
        "team_id": args.team_id,
        "key_alias": "medguard-backend",
        "models": list(DEFAULT_MODELS),
        "max_budget": args.max_budget,
        "budget_duration": args.budget_duration,
        "duration": args.duration,
        "rpm_limit": args.rpm_limit,
        "tpm_limit": args.tpm_limit,
        "max_parallel_requests": args.max_parallel_requests,
        "metadata": {
            "service": "medguard-ai",
            "data_classification": "clinical-sensitive",
        },
    }
    try:
        response = httpx.post(
            f"{_gateway_root(args.gateway_url)}/key/generate",
            headers={
                "Authorization": f"Bearer {args.master_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=args.timeout,
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        print(f"Virtual key generation failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(body, ensure_ascii=False, indent=2))
    print(
        "Store the returned key as MEDGUARD_LLM_GATEWAY_API_KEY; "
        "do not place provider keys in the application environment.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
