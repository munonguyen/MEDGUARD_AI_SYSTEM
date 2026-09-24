"""Run development-only hard-user chat cases against the full API boundary."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.main import app  # noqa: E402


DATASET_PATH = BASE_DIR / "datasets" / "DS-CHAT-HARD" / "dataset.json"
_INTERNAL_TERMS = ("gemini", "litellm", "provider_name", "agent_trace", "orchestrator")


def _at_path(value: Any, dotted_path: str) -> Any:
    current = value
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted_path)
        current = current[part]
    return current


def _case_failures(body: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for path, wanted in expected.get("values", {}).items():
        try:
            actual = _at_path(body, path)
        except KeyError:
            failures.append(f"missing:{path}")
            continue
        if actual != wanted:
            failures.append(f"{path}={actual!r}, expected={wanted!r}")
    for path, wanted in expected.get("lengths", {}).items():
        try:
            actual = _at_path(body, path)
        except KeyError:
            failures.append(f"missing:{path}")
            continue
        if not hasattr(actual, "__len__") or len(actual) != wanted:
            failures.append(f"len({path})={len(actual) if hasattr(actual, '__len__') else 'N/A'}, expected={wanted}")
    for path, fragment in expected.get("contains", {}).items():
        try:
            actual = str(_at_path(body, path)).lower()
        except KeyError:
            failures.append(f"missing:{path}")
            continue
        if str(fragment).lower() not in actual:
            failures.append(f"{path} missing fragment={fragment!r}")
    answer_text = json.dumps(body.get("answer"), ensure_ascii=False).lower()
    for forbidden in expected.get("forbidden_answer", []):
        if forbidden.lower() in answer_text:
            failures.append(f"answer contains forbidden text={forbidden!r}")
    serialized = json.dumps(body, ensure_ascii=False).lower()
    for internal in _INTERNAL_TERMS:
        if internal in serialized:
            failures.append(f"response exposes internal term={internal!r}")
    return failures


def run_chat_hard_benchmark() -> dict[str, Any]:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    metadata = dataset.get("_meta", {})
    if metadata.get("production_evaluable") is not False or metadata.get("training_allowed") is not False:
        raise ValueError("hard-user dataset must remain evaluation-only")
    cases = dataset.get("cases", [])
    if metadata.get("total") != len(cases):
        raise ValueError("hard-user dataset total does not match case count")

    client = TestClient(app)
    results: list[dict[str, Any]] = []
    for case in cases:
        case_id = case["case_id"]
        response = client.post(
            "/v1/chat",
            headers={
                "X-API-Key": "demo-key",
                "X-Tenant-Id": "tenant-demo",
                "X-Consent-Token": "consent-hard-user-benchmark",
                "Idempotency-Key": f"hard-user-{metadata['version']}-{case_id}",
            },
            json={
                "conversation_id": f"hard-user-{metadata['version']}-{case_id}",
                "messages": [{"role": "user", "content": case["prompt"]}],
                "context": case.get("context", {}),
                "intent_hint": case.get("intent_hint", "auto"),
                "locale": case.get("locale", "vi-VN"),
            },
        )
        failures = [] if response.status_code == 200 else [f"http_status={response.status_code}"]
        body = response.json()
        failures.extend(_case_failures(body, case["expected"]))
        results.append(
            {
                "case_id": case_id,
                "category": case["category"],
                "passed": not failures,
                "failures": failures,
            }
        )
    passed = sum(result["passed"] for result in results)
    return {
        "dataset_version": metadata["version"],
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / len(results), 4) if results else 0.0,
        "gate_passed": bool(results) and passed == len(results),
        "production_evaluable": False,
        "results": results,
    }


def main() -> int:
    report = run_chat_hard_benchmark()
    print(
        f"hard_user_cases={report['total']} passed={report['passed']} "
        f"failed={report['failed']} pass_rate={report['pass_rate']:.2%} "
        f"gate={'PASS' if report['gate_passed'] else 'FAIL'}"
    )
    for result in report["results"]:
        if not result["passed"]:
            print(f"{result['case_id']} {result['category']}: {'; '.join(result['failures'])}")
    return 0 if report["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
