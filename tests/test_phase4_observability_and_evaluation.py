"""Unit Tests for Phase 4E & 4F: Observability, Audit, Calibration, and Blind Evaluation."""

import pytest
from app.observability.tracing import ClinicalTrace
from app.observability.audit_store import AuditStore
from app.observability.metrics import (
    compute_brier_score,
    compute_ece,
    compute_cohort_metrics,
    compute_evidence_recall,
    compute_invariance_score,
)
from app.evaluation.corpus_loader import CorpusLoader
from app.evaluation.blind_runner import BlindEvaluationRunner


def test_audit_store_records_and_queries_immutable_traces():
    store = AuditStore(max_capacity=50)

    trace1 = ClinicalTrace(
        ccs_hash="hash_001",
        kb_snapshot_id="2026.09.26.14",
        final_urgency="EMERGENCY",
        arbitration_action="ACCEPT_A",
    )
    trace2 = ClinicalTrace(
        ccs_hash="hash_002",
        kb_snapshot_id="2026.09.26.14",
        final_urgency="ROUTINE",
        arbitration_action="ACCEPT_A",
    )

    store.record_trace(trace1)
    store.record_trace(trace2)

    assert store.get_trace(trace1.trace_id) is not None
    em_traces = store.query(urgency="EMERGENCY")
    assert len(em_traces) == 1
    assert em_traces[0].trace_id == trace1.trace_id


def test_calibration_metrics_brier_and_ece():
    # Perfectly calibrated case
    preds_perfect = [0.9, 0.1]
    targets_perfect = [1, 0]
    brier_perfect = compute_brier_score(preds_perfect, targets_perfect)
    assert brier_perfect < 0.05

    # Poorly calibrated case
    preds_poor = [0.9, 0.8]
    targets_poor = [0, 0]
    brier_poor = compute_brier_score(preds_poor, targets_poor)
    assert brier_poor > 0.50

    # Expected Calibration Error
    ece = compute_ece([0.95, 0.85, 0.2, 0.1], [1, 1, 0, 0], num_bins=5)
    assert 0.0 <= ece <= 1.0


def test_cohort_metrics_calculates_recall_and_specificity():
    preds = ["EMERGENCY", "EMERGENCY", "ROUTINE", "ROUTINE"]
    targets = ["EMERGENCY", "ROUTINE", "EMERGENCY", "ROUTINE"]

    metrics = compute_cohort_metrics(preds, targets, positive_label="EMERGENCY")
    assert metrics["tp"] == 1
    assert metrics["fp"] == 1
    assert metrics["fn"] == 1
    assert metrics["tn"] == 1
    assert metrics["recall"] == 0.5
    assert metrics["specificity"] == 0.5


def test_evidence_recall_and_invariance_score():
    # Evidence recall: E1, E2 required; E1 retrieved -> recall = 0.5
    gold_ids = ["E1_dvt_red_flags", "E2_nsaid_contraindication"]
    retrieved_ids = ["E1_dvt_red_flags", "E3_unrelated"]
    recall = compute_evidence_recall(retrieved_ids, gold_ids)
    assert recall == 0.5

    # Invariance score: 9 out of 10 variations preserve emergency triage -> 90%
    baseline = "EMERGENCY"
    variants = [
        "EMERGENCY", "EMERGENCY", "EMERGENCY", "EMERGENCY", "EMERGENCY",
        "EMERGENCY", "EMERGENCY", "EMERGENCY", "EMERGENCY", "ROUTINE"
    ]
    invariance = compute_invariance_score(variants, baseline)
    assert invariance == 0.90



def test_corpus_loader_and_metamorphic_generation():
    cases = CorpusLoader.load_benchmark_cohort()
    assert len(cases) >= 5

    # Test metamorphic generation
    base_case = cases[0]
    variants = CorpusLoader.generate_metamorphic_variants(base_case)
    assert len(variants) == 2
    assert "casual_teencode" in variants[0].metadata["metamorphic_type"]
    assert "anxious_unpunctuated" in variants[1].metadata["metamorphic_type"]


def test_blind_evaluation_runner_executes_cohort():
    cases = CorpusLoader.load_benchmark_cohort()

    summary = BlindEvaluationRunner.run_cohort(cases)
    assert summary.total_evaluated == len(cases)
    assert summary.emergency_recall >= 0.99
    assert summary.benign_specificity >= 0.95
    assert summary.unsupported_diagnosis_rate == 0.0
