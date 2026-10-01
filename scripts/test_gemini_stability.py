from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


TRANSIENT_HTTP = {408, 429, 500, 502, 503, 504}
EXTERNAL_DEGRADED_HTTP = {429, 500, 502, 503, 504}
ALIASES = (
    ("writer", "medguard-clinical-answer"),
    ("reviewer", "medguard-clinical-verifier"),
)


@dataclass
class Attempt:
    ok: bool
    latency_s: float
    retries: int
    detail: str
    http_status: int | None = None


@dataclass(frozen=True)
class SeriesResult:
    name: str
    status: Literal["pass", "degraded_external", "fail_application"]
    success_count: int
    iterations: int
    retry_count: int
    median_s: float
    p95_s: float
    failures: tuple[str, ...]
    failure_http_statuses: tuple[int | None, ...]

    @property
    def application_ok(self) -> bool:
        return self.status != "fail_application"


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
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int,
) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        return response.status, json.loads(raw or "{}")


def _error_code(exc: Exception) -> int | None:
    return exc.code if isinstance(exc, urllib.error.HTTPError) else None


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    return f"{type(exc).__name__}: {exc}"


def _with_retry(call, *, max_retries: int = 2) -> Attempt:
    start = time.perf_counter()
    retries = 0
    while True:
        try:
            detail = call()
            return Attempt(True, time.perf_counter() - start, retries, detail)
        except Exception as exc:
            code = _error_code(exc)
            if retries >= max_retries or (code is not None and code not in TRANSIENT_HTTP):
                return Attempt(
                    False,
                    time.perf_counter() - start,
                    retries,
                    _safe_error(exc),
                    http_status=code,
                )
            retries += 1
            time.sleep(min(2**retries, 5))


def _direct_once(model: str, key: str, timeout: int) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    status, data = _request_json(
        url,
        headers={"x-goog-api-key": key},
        payload={
            "contents": [{"parts": [{"text": "Reply with exactly STABLE_OK."}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 128},
        },
        timeout=timeout,
    )
    candidates = data.get("candidates") or []
    text = ""
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        text = " ".join(str(part.get("text", "")) for part in parts).strip()
    if status != 200 or not text:
        raise RuntimeError(f"empty/non-200 response: {status}")
    return f"HTTP {status}; nonempty=true"


def _gateway_once(alias: str, token: str, base: str, timeout: int) -> str:
    status, data = _request_json(
        f"{base.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        payload={
            "model": alias,
            "messages": [{"role": "user", "content": "Reply with exactly STABLE_OK."}],
            "temperature": 0,
            "max_tokens": 128,
        },
        timeout=timeout,
    )
    choices = data.get("choices") or []
    text = choices[0].get("message", {}).get("content", "") if choices else ""
    if status != 200 or not str(text).strip():
        raise RuntimeError(f"empty/non-200 response: {status}")
    return f"HTTP {status}; nonempty=true"


def _p95(values: list[float]) -> float:
    if not values:
        return float("inf")
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
    return ordered[index]


def _run_series(name: str, fn, *, iterations: int, max_p95_s: float) -> SeriesResult:
    attempts = [_with_retry(fn) for _ in range(iterations)]
    successes = [item for item in attempts if item.ok]
    failures = [item for item in attempts if not item.ok]
    latencies = [item.latency_s for item in successes]
    success_rate = len(successes) / iterations
    retry_count = sum(item.retries for item in attempts)
    median = statistics.median(latencies) if latencies else float("inf")
    p95 = _p95(latencies)

    if success_rate == 1.0 and p95 <= max_p95_s:
        status: Literal["pass", "degraded_external", "fail_application"] = "pass"
    elif failures and all(item.http_status in EXTERNAL_DEGRADED_HTTP for item in failures):
        status = "degraded_external"
    else:
        status = "fail_application"

    marker = {
        "pass": "PASS",
        "degraded_external": "DEGRADED_EXTERNAL",
        "fail_application": "FAIL_APPLICATION",
    }[status]
    print(
        f"[{marker}] {name}: success={len(successes)}/{iterations} "
        f"rate={success_rate:.0%} retries={retry_count} median={median:.2f}s p95={p95:.2f}s"
    )
    for index, item in enumerate(attempts, 1):
        if not item.ok:
            print(f"  attempt {index}: {item.detail}")

    return SeriesResult(
        name=name,
        status=status,
        success_count=len(successes),
        iterations=iterations,
        retry_count=retry_count,
        median_s=median,
        p95_s=p95,
        failures=tuple(item.detail for item in failures),
        failure_http_statuses=tuple(item.http_status for item in failures),
    )


def _write_report(path: Path | None, results: list[SeriesResult], *, configured: bool) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    overall = "pass"
    if any(item.status == "fail_application" for item in results) or not configured:
        overall = "fail_application"
    elif any(item.status == "degraded_external" for item in results):
        overall = "degraded_external"
    payload = {
        "gate": "GEMINI_PROVIDER_READINESS",
        "configured": configured,
        "status": overall,
        "application_certification_passed": configured
        and not any(item.status == "fail_application" for item in results),
        "provider_fully_ready": configured and all(item.status == "pass" for item in results),
        "series": [
            {
                "name": item.name,
                "status": item.status,
                "success_count": item.success_count,
                "iterations": item.iterations,
                "retry_count": item.retry_count,
                "median_s": None if item.median_s == float("inf") else round(item.median_s, 4),
                "p95_s": None if item.p95_s == float("inf") else round(item.p95_s, 4),
                "failures": list(item.failures),
                "failure_http_statuses": list(item.failure_http_statuses),
            }
            for item in results
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Repeated Gemini/LiteLLM stability certification.")
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--gateway", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument(
        "--allow-external-degraded",
        action="store_true",
        help=(
            "Exit successfully for provider-side quota/5xx degradation while still emitting a "
            "DEGRADED_EXTERNAL result. Application/protocol failures continue to fail."
        ),
    )
    parser.add_argument(
        "--writer-model",
        default=os.getenv("MEDGUARD_STABILITY_WRITER_MODEL", "gemini-3.5-flash-lite"),
        help="Direct API model used by the mandatory Writer path.",
    )
    parser.add_argument(
        "--reviewer-model",
        default=os.getenv("MEDGUARD_STABILITY_REVIEWER_MODEL", "gemini-3.5-flash-lite"),
        help="Direct API model used by the non-authoring Reviewer path.",
    )
    args = parser.parse_args()

    if args.iterations < 3:
        parser.error("--iterations must be at least 3")
    if not any((args.direct, args.gateway, args.all)):
        args.all = True

    root = Path(__file__).resolve().parents[1]
    _load_env_file(root / "infrastructure" / "litellm" / ".env")
    _load_env_file(root / ".env")

    models = (
        ("writer", args.writer_model),
        ("reviewer", args.reviewer_model),
    )
    results: list[SeriesResult] = []
    configured = True

    if args.all or args.direct:
        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key:
            print("[FAIL_APPLICATION] direct Gemini: GEMINI_API_KEY is not configured")
            configured = False
        else:
            for role, model in models:
                results.append(
                    _run_series(
                        f"direct {role} {model}",
                        lambda model=model: _direct_once(model, key, args.timeout),
                        iterations=args.iterations,
                        max_p95_s=30.0,
                    )
                )

    if args.all or args.gateway:
        token = os.getenv("MEDGUARD_LLM_GATEWAY_API_KEY", "").strip()
        base = os.getenv("MEDGUARD_LLM_GATEWAY_URL", "http://127.0.0.1:4000/v1")
        if not token:
            print("[FAIL_APPLICATION] LiteLLM gateway: MEDGUARD_LLM_GATEWAY_API_KEY is not configured")
            configured = False
        else:
            for role, alias in ALIASES:
                results.append(
                    _run_series(
                        f"gateway {role} {alias}",
                        lambda alias=alias: _gateway_once(alias, token, base, args.timeout),
                        iterations=args.iterations,
                        max_p95_s=35.0,
                    )
                )

    _write_report(args.report, results, configured=configured)

    application_failure = (not configured) or any(
        result.status == "fail_application" for result in results
    )
    external_degraded = any(result.status == "degraded_external" for result in results)
    if application_failure:
        return 1
    if external_degraded and not args.allow_external_degraded:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
