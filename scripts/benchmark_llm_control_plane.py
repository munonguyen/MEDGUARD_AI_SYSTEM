"""Benchmark deterministic LLM policy, isolation and single-flight behavior."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import math
from pathlib import Path
import sys
import threading
from time import perf_counter, sleep

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.services.llm_control_plane import (  # noqa: E402
    SingleFlightCoordinator,
    gateway_controls,
    policy_for_intent,
)


def _percentile(values: list[float], value: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * value) - 1)] if ordered else 0.0


def run_llm_control_plane_benchmark(iterations: int = 2_000, workers: int = 20) -> dict:
    latencies: list[float] = []
    scopes: set[str] = set()
    secrets = ("tenant-sensitive", "patient-sensitive", "conversation-sensitive")
    intents = ("triage", "safety", "monitoring", "followup", "pharmacy", "authenticity")

    for index in range(iterations):
        intent = intents[index % len(intents)]
        start = perf_counter()
        controls = gateway_controls(
            role="answer" if index % 2 == 0 else "verifier",
            policy=policy_for_intent(intent),  # type: ignore[arg-type]
            tenant_id=f"tenant-sensitive-{index % 17}",
            conversation_id=f"conversation-sensitive-{index}",
            locale="vi-VN",
            patient_context={"patient_ref": f"patient-sensitive-{index}", "age": index % 100},
            prompt_version="benchmark-prompt-v1",
            knowledge_version=f"benchmark-knowledge-v{index % 3}",
            tool_result={"status": "registry_match", "index": index},
            instructions="Use bounded approved claims only.",
            payload={"intent": intent, "index": index},
            max_input_tokens=12_000,
            max_output_tokens=2_400,
        )
        latencies.append((perf_counter() - start) * 1000)
        scopes.add(controls.cache_scope)
        visible = " ".join(
            (controls.cache_namespace, controls.cache_scope, controls.end_user_scope, controls.session_scope)
        )
        if any(secret in visible for secret in secrets):
            raise AssertionError("control-plane scope exposed a raw identity")

    coordinator = SingleFlightCoordinator(redis_url=None, timeout_seconds=2)
    barrier = threading.Barrier(workers)
    lock = threading.Lock()
    operation_calls = 0

    def operation() -> str:
        nonlocal operation_calls
        with lock:
            operation_calls += 1
        sleep(0.03)
        return "verified"

    def invoke() -> str:
        barrier.wait()
        return coordinator.run("benchmark-safe-flight", operation)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(lambda _index: invoke(), range(workers)))

    p95 = round(_percentile(latencies, 0.95), 4)
    return {
        "iterations": iterations,
        "unique_scopes": len(scopes),
        "scope_collision_count": iterations - len(scopes),
        "policy_p95_ms": p95,
        "singleflight_callers": workers,
        "singleflight_operations": operation_calls,
        "all_passed": (
            len(scopes) == iterations
            and p95 <= 5.0
            and operation_calls == 1
            and results == ["verified"] * workers
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=2_000)
    parser.add_argument("--workers", type=int, default=20)
    args = parser.parse_args()
    if args.iterations < 1 or args.workers < 2:
        parser.error("iterations must be >= 1 and workers must be >= 2")
    report = run_llm_control_plane_benchmark(args.iterations, args.workers)
    print(
        f"llm_control_plane={'PASS' if report['all_passed'] else 'FAIL'} "
        f"iterations={report['iterations']} unique_scopes={report['unique_scopes']} "
        f"collisions={report['scope_collision_count']} policy_p95_ms={report['policy_p95_ms']} "
        f"singleflight={report['singleflight_operations']}/{report['singleflight_callers']}"
    )
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
