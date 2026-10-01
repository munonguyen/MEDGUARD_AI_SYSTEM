from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> tuple[int, dict[str, Any]]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    merged_headers = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        merged_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=merged_headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        return response.status, json.loads(raw or "{}")


def _error_detail(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        try:
            raw = exc.read().decode("utf-8")
            payload = json.loads(raw)
            message = payload.get("error", {}).get("message")
            if message:
                return f"HTTP {exc.code}: {message}"
        except Exception:
            pass
        return f"HTTP {exc.code}"
    return f"{type(exc).__name__}: {exc}"


def check_direct_gemini() -> list[CheckResult]:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return [CheckResult("Gemini direct", False, "GEMINI_API_KEY is not configured")]

    results: list[CheckResult] = []
    for model in ("gemini-3.8-flash", "gemini-3.5-flash-lite"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": "Reply with exactly OK."}]}],
            "generationConfig": {"maxOutputTokens": 128, "temperature": 0},
        }
        try:
            status, data = _request_json(
                url,
                method="POST",
                headers={"x-goog-api-key": key},
                payload=payload,
                timeout=45,
            )
            if status == 429:
                time.sleep(10)
                status, data = _request_json(
                    url,
                    method="POST",
                    headers={"x-goog-api-key": key},
                    payload=payload,
                    timeout=45,
                )
            text = ""
            candidates = data.get("candidates") or []
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text = " ".join(str(part.get("text", "")) for part in parts).strip()
            results.append(
                CheckResult(
                    f"Gemini direct {model}",
                    status == 200 and bool(text),
                    f"HTTP {status}; response={text[:80]!r}",
                )
            )
        except Exception as exc:
            results.append(CheckResult(f"Gemini direct {model}", False, _error_detail(exc)))
    return results


def check_gateway() -> list[CheckResult]:
    base = os.getenv("MEDGUARD_LLM_GATEWAY_URL", "http://127.0.0.1:4000/v1").rstrip("/")
    token = os.getenv("MEDGUARD_LLM_GATEWAY_API_KEY", "").strip()
    if not token:
        return [CheckResult("LiteLLM gateway", False, "MEDGUARD_LLM_GATEWAY_API_KEY is not configured")]

    results: list[CheckResult] = []
    for alias in ("medguard-clinical-answer", "medguard-clinical-verifier"):
        try:
            status, data = _request_json(
                f"{base}/chat/completions",
                method="POST",
                headers={"Authorization": f"Bearer {token}"},
                payload={
                    "model": alias,
                    "messages": [{"role": "user", "content": "Reply with exactly OK."}],
                    "temperature": 0,
                    "max_tokens": 128,
                },
                timeout=60,
            )
            choices = data.get("choices") or []
            text = choices[0].get("message", {}).get("content", "") if choices else ""
            results.append(
                CheckResult(
                    f"LiteLLM {alias}",
                    status == 200 and bool(str(text).strip()),
                    f"HTTP {status}; response={str(text)[:80]!r}",
                )
            )
        except Exception as exc:
            results.append(CheckResult(f"LiteLLM {alias}", False, _error_detail(exc)))
    return results


def check_medguard() -> list[CheckResult]:
    base = os.getenv("MEDGUARD_SMOKE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    tenant = os.getenv("MEDGUARD_SMOKE_TENANT", "tenant-demo")
    api_key = os.getenv("MEDGUARD_SMOKE_API_KEY", "demo-key")
    payload = {
        "conversation_id": "v27-1-gemini-smoke",
        "messages": [
            {
                "role": "user",
                "content": "Tôi hơi tức cơ ngực sau buổi tập gym tối qua, ấn vào thì đau hơn.",
            }
        ],
        "intent_hint": "auto",
        "locale": "vi-VN",
    }
    try:
        headers = {
            "X-Tenant-ID": tenant,
            "X-API-Key": api_key,
            "Idempotency-Key": f"smoke-gemini-{uuid.uuid4().hex[:8]}",
            "X-Consent-Token": "consent-smoke-test",
        }
        status, data = _request_json(
            f"{base}/v1/chat",
            method="POST",
            headers=headers,
            payload=payload,
            timeout=90,
        )
        verification = str(data.get("verification_status", ""))
        origin = str(data.get("answer_origin", ""))
        answer = data.get("answer") or {}
        narrative = answer.get("narrative") or []
        visible = "\n".join(str(block.get("text", "")) for block in narrative if isinstance(block, dict)).strip()
        if not visible:
            visible = str(data.get("reply", "")).strip()
        ok = status == 200 and verification == "verified" and origin == "gateway_verified" and bool(visible)
        detail = (
            f"HTTP {status}; verification_status={verification!r}; "
            f"answer_origin={origin!r}; response={visible[:180]!r}"
        )
        return [CheckResult("MedGuard Writer->Reviewer runtime", ok, detail)]
    except Exception as exc:
        return [CheckResult("MedGuard Writer->Reviewer runtime", False, _error_detail(exc))]


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test V27.1 Gemini free runtime without printing secrets.")
    parser.add_argument("--direct", action="store_true", help="Test Gemini Developer API directly")
    parser.add_argument("--gateway", action="store_true", help="Test LiteLLM Writer/Reviewer aliases")
    parser.add_argument("--medguard", action="store_true", help="Test patient-visible MedGuard /v1/chat path")
    parser.add_argument("--all", action="store_true", help="Run all checks")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    _load_env_file(root / "infrastructure" / "litellm" / ".env")
    _load_env_file(root / ".env")

    if not any((args.direct, args.gateway, args.medguard, args.all)):
        args.all = True

    checks: list[CheckResult] = []
    if args.all or args.direct:
        checks.extend(check_direct_gemini())
    if args.all or args.gateway:
        checks.extend(check_gateway())
    if args.all or args.medguard:
        checks.extend(check_medguard())

    failed = False
    for item in checks:
        marker = "PASS" if item.ok else "FAIL"
        print(f"[{marker}] {item.name}: {item.detail}")
        failed = failed or not item.ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
