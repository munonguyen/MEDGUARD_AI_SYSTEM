"""Small repeatable API latency smoke benchmark for development architecture."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from time import perf_counter, perf_counter_ns
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient

from app.main import app


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def run_runtime_benchmark(iterations_per_endpoint: int = 50) -> dict[str, Any]:
    client = TestClient(app)
    run_id = perf_counter_ns()
    scenarios = (
        (
            "triage",
            "/v1/triage",
            {"patient_ref": "perf-triage", "symptoms_text": "dau dau va chong mat"},
        ),
        (
            "safety",
            "/v1/medication/safety-check",
            {
                "patient_ref": "perf-safety",
                "current_medications": [{"name": "Warfarin", "active_ingredient": "warfarin"}],
                "proposed_medications": [{"name": "Aspirin", "active_ingredient": "aspirin"}],
            },
        ),
        (
            "monitoring",
            "/v1/monitoring/ingest",
            {
                "patient_ref": "perf-monitoring",
                "metrics": [
                    {"metric": "spo2", "value": 98, "unit": "%", "recorded_at": "2026-09-07T08:00:00Z"},
                    {"metric": "spo2", "value": 97, "unit": "%", "recorded_at": "2026-09-07T09:00:00Z"},
                    {"metric": "spo2", "value": 96, "unit": "%", "recorded_at": "2026-09-07T10:00:00Z"},
                ],
            },
        ),
    )
    endpoint_results: dict[str, dict[str, float | int]] = {}
    total_errors = 0
    total_requests = len(scenarios) * iterations_per_endpoint
    suite_start = perf_counter()

    for name, path, payload in scenarios:
        latencies_ms: list[float] = []
        errors = 0
        for index in range(iterations_per_endpoint):
            headers = {
                "X-API-Key": "demo-key",
                "X-Tenant-Id": "tenant-demo",
                "Idempotency-Key": f"perf-{run_id}-{name}-{index}",
            }
            started = perf_counter()
            response = client.post(path, headers=headers, json=payload)
            latencies_ms.append((perf_counter() - started) * 1000)
            if response.status_code != 200:
                errors += 1
        total_errors += errors
        endpoint_results[name] = {
            "requests": iterations_per_endpoint,
            "errors": errors,
            "p50_ms": round(_percentile(latencies_ms, 0.50), 3),
            "p95_ms": round(_percentile(latencies_ms, 0.95), 3),
            "max_ms": round(max(latencies_ms), 3),
        }

    elapsed = perf_counter() - suite_start
    max_p95_ms = max(float(result["p95_ms"]) for result in endpoint_results.values())
    return {
        "iterations_per_endpoint": iterations_per_endpoint,
        "total_requests": total_requests,
        "total_errors": total_errors,
        "throughput_requests_per_second": round(total_requests / elapsed, 2),
        "max_endpoint_p95_ms": round(max_p95_ms, 3),
        "development_gate_passed": total_errors == 0 and max_p95_ms <= 100.0,
        "endpoints": endpoint_results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=50)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("iterations must be >= 1")
    result = run_runtime_benchmark(args.iterations)
    print(
        f"requests={result['total_requests']} errors={result['total_errors']} "
        f"throughput_rps={result['throughput_requests_per_second']} "
        f"max_p95_ms={result['max_endpoint_p95_ms']} "
        f"gate={'PASS' if result['development_gate_passed'] else 'FAIL'}"
    )
    for endpoint, metrics in result["endpoints"].items():
        print(
            f"endpoint={endpoint} p50_ms={metrics['p50_ms']} "
            f"p95_ms={metrics['p95_ms']} max_ms={metrics['max_ms']} errors={metrics['errors']}"
        )
    raise SystemExit(0 if result["development_gate_passed"] else 1)
