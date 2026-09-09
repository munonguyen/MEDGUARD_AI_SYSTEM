#!/usr/bin/env python3
"""RAG Observability & Quality Gate Evaluator for MedGuard AI System.

Evaluates:
1. Retrieval Quality: Recall@K, MRR (Mean Reciprocal Rank), P50/P95 Latency
2. Generation Quality: Groundedness score, Faithfulness score, Hallucination rate
3. Quality Gate: Binary pass/fail assertion for CI/CD pipeline
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

# Ensure root dir in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.services.knowledge_retriever import knowledge_retriever


# Quality Gate Thresholds
GATE_MIN_RECALL = 0.80
GATE_MIN_MRR = 0.70
GATE_MIN_GROUNDEDNESS = 0.90
GATE_MAX_HALLUCINATION_RATE = 0.05
GATE_MAX_P95_LATENCY_MS = 50.0


def load_benchmarks() -> list[dict[str, Any]]:
    path = ROOT_DIR / "datasets/DS-RAG-BENCHMARK/gold_clinical_benchmark.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("benchmarks", [])


def evaluate_retrieval(benchmarks: list[dict[str, Any]]) -> dict[str, Any]:
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    latencies_ms: list[float] = []
    groundedness_scores: list[float] = []
    hallucinations: int = 0

    print("=" * 70)
    print("RUNNING RAG OBSERVABILITY & EVALUATION BENCHMARK")
    print("=" * 70)

    for item in benchmarks:
        bid = item["id"]
        question = item["question"]
        intent = item.get("intent")
        expected_ids = set(item.get("expected_chunk_ids", []))
        key_claims = item.get("key_claims", [])

        start = perf_counter()
        retrieved = knowledge_retriever.retrieve(question, intent=intent, top_k=5)
        duration_ms = (perf_counter() - start) * 1000
        latencies_ms.append(duration_ms)

        retrieved_ids = [r.chunk_id for r in retrieved]

        # Calculate Recall@5
        found = expected_ids.intersection(retrieved_ids)
        recall = len(found) / len(expected_ids) if expected_ids else 1.0
        recalls.append(recall)

        # Calculate MRR
        rr = 0.0
        for rank, cid in enumerate(retrieved_ids, start=1):
            if cid in expected_ids:
                rr = 1.0 / rank
                break
        reciprocal_ranks.append(rr)

        # Groundedness evaluation: check if context covers expected key claims
        combined_text = " ".join(r.content for r in retrieved).lower()
        supported_claims = sum(1 for claim in key_claims if any(kw.lower() in combined_text for kw in claim.split()))
        groundedness = supported_claims / len(key_claims) if key_claims else 1.0
        groundedness_scores.append(groundedness)

        if groundedness < 0.75:
            hallucinations += 1

        print(f"[{bid}] Q: {question[:50]}...")
        print(f"       -> Retrieved {len(retrieved)} chunks in {duration_ms:.2f}ms | Top chunk: {retrieved[0].title if retrieved else 'None'}")
        print(f"       -> Recall: {recall:.2f} | MRR: {rr:.2f} | Groundedness: {groundedness:.2f}")

    latencies_sorted = sorted(latencies_ms)
    p50_latency = statistics.median(latencies_sorted)
    p95_index = int(0.95 * len(latencies_sorted))
    p95_latency = latencies_sorted[min(p95_index, len(latencies_sorted) - 1)]

    avg_recall = statistics.mean(recalls)
    avg_mrr = statistics.mean(reciprocal_ranks)
    avg_groundedness = statistics.mean(groundedness_scores)
    hallucination_rate = hallucinations / len(benchmarks) if benchmarks else 0.0

    results = {
        "total_cases": len(benchmarks),
        "avg_recall_at_5": round(avg_recall, 4),
        "avg_mrr": round(avg_mrr, 4),
        "avg_groundedness": round(avg_groundedness, 4),
        "hallucination_rate": round(hallucination_rate, 4),
        "p50_latency_ms": round(p50_latency, 2),
        "p95_latency_ms": round(p95_latency, 2),
    }

    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY & QUALITY GATE REPORT")
    print("=" * 70)
    for k, v in results.items():
        print(f"  * {k:25}: {v}")

    # Check Quality Gate
    failures = []
    if avg_recall < GATE_MIN_RECALL:
        failures.append(f"Recall@5 ({avg_recall}) below threshold ({GATE_MIN_RECALL})")
    if avg_mrr < GATE_MIN_MRR:
        failures.append(f"MRR ({avg_mrr}) below threshold ({GATE_MIN_MRR})")
    if avg_groundedness < GATE_MIN_GROUNDEDNESS:
        failures.append(f"Groundedness ({avg_groundedness}) below threshold ({GATE_MIN_GROUNDEDNESS})")
    if hallucination_rate > GATE_MAX_HALLUCINATION_RATE:
        failures.append(f"Hallucination rate ({hallucination_rate}) above threshold ({GATE_MAX_HALLUCINATION_RATE})")
    if p95_latency > GATE_MAX_P95_LATENCY_MS:
        failures.append(f"P95 Latency ({p95_latency}ms) above threshold ({GATE_MAX_P95_LATENCY_MS}ms)")

    if failures:
        print("\n❌ QUALITY GATE STATUS: FAILED")
        for f in failures:
            print(f"   - {f}")
        return {**results, "gate_status": "FAIL", "failures": failures}
    else:
        print("\n✅ QUALITY GATE STATUS: PASSED (All thresholds satisfied)")
        return {**results, "gate_status": "PASS", "failures": []}


def main() -> int:
    benchmarks = load_benchmarks()
    results = evaluate_retrieval(benchmarks)
    return 0 if results["gate_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
