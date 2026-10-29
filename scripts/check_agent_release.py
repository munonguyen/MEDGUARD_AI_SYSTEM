"""Live end-to-end check using synthetic complaints; no raw answers/secrets printed."""
from __future__ import annotations

import json
import os
import sys
from uuid import uuid4

import httpx

QUESTIONS = (
    "Tôi bị đau ngực lan tay trái và khó thở, cần hỗ trợ ngay.",
    "Tôi đang đau răng cần làm gì để khỏi",
    "Tôi đang đau ruột thừa có nên đi mổ sớm không",
)


def check_release(client: httpx.Client, root: str, headers: dict) -> dict:
    conversation = "synthetic-release-" + uuid4().hex
    messages = []
    report = {"passed": False, "turns": [], "production_ready": False}
    for index, question in enumerate(QUESTIONS):
        messages.append({"role": "user", "content": question})
        response = client.post(root + "/v1/chat", headers={
            **headers, "Idempotency-Key": uuid4().hex,
        }, json={"conversation_id": conversation, "messages": messages, "locale": "vi-VN"})
        response.raise_for_status()
        data = response.json()
        execution = data.get("agent_execution") or {}
        urgency = (data.get("result") or {}).get("urgency")
        answer = data.get("answer") or {}
        answer_text = json.dumps(answer, ensure_ascii=False).lower()
        valid = (
            data.get("verification_status") == "verified"
            and data.get("answer_origin") == "gateway_verified"
            and execution.get("requested") is True
            and execution.get("writer") == "success"
            and execution.get("reviewer") == "success"
            and bool(answer.get("narrative"))
            and bool(answer.get("answer_assurance"))
        )
        if index == 0:
            valid = valid and urgency == "EMERGENCY" and "115" in data.get("reply", "") and "115" in answer_text
        if index == 1:
            valid = valid and urgency == "ROUTINE" and any(word in answer_text for word in ("răng", "nha sĩ"))
        if index == 2:
            valid = valid and urgency in {"URGENT", "EMERGENCY"}
            valid = valid and "nha sĩ" not in answer_text
        report["turns"].append({"turn": index + 1, "request_id": data.get("request_id"),
            "verified": bool(valid), "writer": execution.get("writer", "unknown"),
            "reviewer": execution.get("reviewer", "unknown"), "urgency": urgency,
            "reason": execution.get("reason")})
        messages.append({"role": "assistant", "content": data.get("reply") or "No answer"})
    response = client.get(root + "/v1/health/readiness", headers=headers)
    response.raise_for_status()
    readiness = response.json()
    report["production_ready"] = readiness.get("production_ready") is True
    report["failed_readiness_checks"] = [c.get("name") for c in readiness.get("checks", [])
        if c.get("required_for_production", True) and c.get("status") != "pass"]
    report["passed"] = all(t["verified"] for t in report["turns"]) and report["production_ready"] and not report["failed_readiness_checks"]
    return report


def main() -> int:
    names = ("MEDGUARD_API_URL", "MEDGUARD_API_KEY", "MEDGUARD_TENANT_ID", "MEDGUARD_CONSENT_TOKEN")
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        print(json.dumps({"passed": False, "missing_environment": missing}))
        return 2
    headers = {"X-API-Key": os.environ[names[1]], "X-Tenant-Id": os.environ[names[2]],
        "X-Consent-Token": os.environ[names[3]]}
    try:
        with httpx.Client(timeout=35) as client:
            report = check_release(client, os.environ[names[0]].rstrip("/").removesuffix("/v1"), headers)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, ImportError):
        # Provider URLs or raw server messages can contain secrets or PHI.
        print(json.dumps({"passed": False, "error": "transport_or_response_contract_failure"}))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
