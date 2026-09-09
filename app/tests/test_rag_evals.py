"""Tests for RAG Observability, Retrieval Quality and CI/CD Quality Gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.observability import metrics
from app.services.knowledge_retriever import knowledge_retriever
from scripts.eval_ragas_quality_gate import (
    GATE_MAX_HALLUCINATION_RATE,
    GATE_MIN_GROUNDEDNESS,
    GATE_MIN_MRR,
    GATE_MIN_RECALL,
    evaluate_retrieval,
    load_benchmarks,
)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def test_knowledge_retriever_indices_built():
    assert len(knowledge_retriever._chunks) > 50
    assert len(knowledge_retriever._token_index) > 100
    assert len(knowledge_retriever._idf) > 100

    # Test retrieval of specific drug interaction
    results = knowledge_retriever.retrieve("sildenafil nitroglycerin", intent="safety", top_k=3)
    assert len(results) > 0
    assert results[0].chunk_id == "INT-sildenafil-nitroglycerin"
    assert "HARD_STOP" in results[0].content


def test_knowledge_retriever_intent_isolation():
    # Triage query should prioritize red flag protocols
    triage_results = knowledge_retriever.retrieve("ngừng tuần hoàn hô mê sâu", intent="triage", top_k=3)
    assert len(triage_results) > 0
    assert all(r.doc_name == "red_flag_protocols.json" for r in triage_results)


def test_gold_clinical_benchmark_file_validity():
    benchmarks = load_benchmarks()
    assert len(benchmarks) >= 6
    for b in benchmarks:
        assert "id" in b
        assert "question" in b
        assert "expected_chunk_ids" in b
        assert "key_claims" in b
        assert "ground_truth" in b


def test_rag_quality_gate_passes_all_thresholds():
    benchmarks = load_benchmarks()
    summary = evaluate_retrieval(benchmarks)

    assert summary["gate_status"] == "PASS", f"Quality gate failed: {summary.get('failures')}"
    assert summary["avg_recall_at_5"] >= GATE_MIN_RECALL
    assert summary["avg_mrr"] >= GATE_MIN_MRR
    assert summary["avg_groundedness"] >= GATE_MIN_GROUNDEDNESS
    assert summary["hallucination_rate"] <= GATE_MAX_HALLUCINATION_RATE
    assert summary["p95_latency_ms"] < 50.0  # Under 50ms requirement


def test_rag_prometheus_metrics_exported():
    # Trigger a retrieval to ensure metric observation
    knowledge_retriever.retrieve("metformin suy thận", intent="safety")
    metrics.set_gauge("medguard_rag_groundedness_score", 0.95)
    metrics.set_gauge("medguard_rag_safety_score", 0.98)
    metrics.inc_counter("medguard_rag_hallucinations_detected_total", 0.0)

    rendered = metrics.render()
    assert "medguard_rag_retrieval_latency_seconds_count" in rendered
    assert "medguard_rag_retrieval_chunks_count_count" in rendered
    assert "medguard_rag_groundedness_score" in rendered
    assert "medguard_rag_safety_score" in rendered
