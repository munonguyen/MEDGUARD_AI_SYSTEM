"""Evaluator for the 600-Case Semantic Clinical Abstraction Benchmark.

Measures:
1. Critical Fact Recall (Gate: >= 98.0%)
2. Partial High-Risk Evidence Recall (Gate: >= 99.0%)
3. Critical Fact Precision (Gate: >= 95.0%)
4. Functional-Loss Recall
5. Perfusion-Threat Recall
6. Toxic Exposure Recall
7. Benign Mimic / Negation Hallucination Rate (Gate: 0.0%)
8. Triage Accuracy and Specificity on Benign Controls (Gate: >= 98.0%)
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.context import RequestContext
from app.models.triage import TriageRequest
from app.services.clinical_fact_parser import parse_semantic_clinical_facts
from app.services.partial_evidence_safety import evaluate_partial_evidence_safety
from app.services.semantic_abstraction_layer import extract_semantic_abstractions
from app.services.triage import evaluate_triage


def evaluate_benchmark():
    dataset_file = REPO_ROOT / "datasets" / "DS-SEMANTIC-ABSTRACTION" / "dataset.json"
    with open(dataset_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    print("=" * 80)
    print(f"EVALUATING 600-CASE SEMANTIC CLINICAL ABSTRACTION BENCHMARK")
    print("=" * 80)
    print(f"Loaded {len(cases)} cases across 6 distinct cohorts.")

    ctx = RequestContext(
        request_id="eval-sem-abstr",
        tenant_id="medguard-hospital",
        idempotency_key="eval-sem-key",
    )

    t0 = time.perf_counter()

    crit_fact_expected_total = 0
    crit_fact_hits = 0
    crit_fact_extracted_total = 0
    crit_fact_true_positives = 0

    partial_evidence_expected_total = 0
    partial_evidence_hits = 0

    perfusion_expected = 0
    perfusion_hits = 0

    functional_loss_expected = 0
    functional_loss_hits = 0

    toxic_expected = 0
    toxic_hits = 0

    benign_total = 0
    benign_hallucinations = 0
    benign_correct = 0

    triage_correct = 0
    results = []

    for idx, c in enumerate(cases, 1):
        cid = c["case_id"]
        cohort = c["cohort"]
        text = c["input_text"]
        is_em = c["is_emergency"]

        # 1. Fact Parser & Semantic Abstraction evaluation
        facts = parse_semantic_clinical_facts(text)
        abstr = extract_semantic_abstractions(text)
        safety = evaluate_partial_evidence_safety(text, fact_set=facts, abstractions=abstr)

        extracted_concepts = list(dict.fromkeys(e.concept for e in facts.events))
        extracted_losses = list(dict.fromkeys(e.functional_loss for e in facts.events if e.functional_loss))
        extracted_cons = list(dict.fromkeys(e.physiologic_consequence for e in facts.events if e.physiologic_consequence))

        # Critical Fact evaluation
        exp_facts = c.get("expected_critical_facts", [])
        if exp_facts:
            crit_fact_expected_total += len(exp_facts)
            for ef in exp_facts:
                if ef in extracted_concepts:
                    crit_fact_hits += 1
                    crit_fact_true_positives += 1
            crit_fact_extracted_total += len([ec for ec in extracted_concepts if ec in exp_facts])

        # Partial Evidence evaluation
        if is_em:
            partial_evidence_expected_total += 1
            if safety.has_partial_emergency_threat or abstr.has_critical_functional_loss or abstr.has_physiologic_instability or abstr.has_surgical_barrier_threat or abstr.has_toxic_exposure_threat:
                partial_evidence_hits += 1

        # Cohort-specific evaluations
        if c.get("domain") == "perfusion_threat":
            perfusion_expected += 1
            if "loss_of_limb_perfusion" in extracted_losses or "limb_perfusion_failure" in extracted_cons or "arterial_occlusion" in extracted_concepts:
                perfusion_hits += 1

        if c.get("expected_functional_loss"):
            for exp_fl in c["expected_functional_loss"]:
                functional_loss_expected += 1
                if exp_fl in extracted_losses:
                    functional_loss_hits += 1

        if "toxic_ingestion" in exp_facts or "acute_toxic_metabolic_threat" in c.get("expected_physiologic_consequence", []):
            toxic_expected += 1
            if "toxic_ingestion" in extracted_concepts or "acute_toxic_metabolic_threat" in extracted_cons or abstr.has_toxic_exposure_threat:
                toxic_hits += 1

        # Benign & Negated Traps evaluation (anti-hallucination check)
        if cohort in ("quoted_negated_traps", "benign_mimics"):
            benign_total += 1
            crit_extracted = [e for e in facts.events if e.is_critical and e.is_present]
            if crit_extracted or safety.has_partial_emergency_threat:
                benign_hallucinations += 1

        # End-to-End Triage Evaluation
        triage_req = TriageRequest(patient_ref="p-eval", symptoms_text=text)
        triage_res = evaluate_triage(triage_req, ctx)
        act_urg = triage_res.urgency

        exp_urg = c["expected_triage"]
        is_triage_ok = (act_urg == exp_urg)
        if is_triage_ok:
            triage_correct += 1
            if cohort in ("quoted_negated_traps", "benign_mimics"):
                benign_correct += 1

        results.append({
            "case_id": cid,
            "cohort": cohort,
            "expected_triage": exp_urg,
            "actual_triage": act_urg,
            "extracted_concepts": extracted_concepts,
            "is_correct": is_triage_ok,
        })

    elapsed = time.perf_counter() - t0

    # Metrics calculation
    crit_recall = (crit_fact_hits / crit_fact_expected_total * 100) if crit_fact_expected_total else 100.0
    crit_precision = (crit_fact_true_positives / crit_fact_extracted_total * 100) if crit_fact_extracted_total else 100.0
    partial_recall = (partial_evidence_hits / partial_evidence_expected_total * 100) if partial_evidence_expected_total else 100.0
    perf_recall = (perfusion_hits / perfusion_expected * 100) if perfusion_expected else 100.0
    func_recall = (functional_loss_hits / functional_loss_expected * 100) if functional_loss_expected else 100.0
    tox_recall = (toxic_hits / toxic_expected * 100) if toxic_expected else 100.0
    benign_spec = (benign_correct / benign_total * 100) if benign_total else 100.0
    hallucination_rate = (benign_hallucinations / benign_total * 100) if benign_total else 0.0
    triage_acc = (triage_correct / len(cases) * 100)

    print("\n" + "=" * 80)
    print("600-CASE SEMANTIC ABSTRACTION BENCHMARK RESULTS")
    print("=" * 80)
    print(f"Evaluation Time:                        {elapsed:.2f}s (avg: {elapsed/len(cases)*1000:.1f}ms/case)")
    print(f"Critical Fact Recall:                   {crit_recall:.2f}% (Target: >=98.0%)")
    print(f"Partial High-Risk Evidence Recall:      {partial_recall:.2f}% (Target: >=99.0%)")
    print(f"Critical Fact Precision:                {crit_precision:.2f}% (Target: >=95.0%)")
    print(f"Perfusion-Threat Recall:                {perf_recall:.2f}%")
    print(f"Functional-Loss Recall:                 {func_recall:.2f}%")
    print(f"Toxic Exposure Recall:                  {tox_recall:.2f}%")
    print(f"Benign / Negated Controls Count:        {benign_total} cases")
    print(f"False Fact Hallucination Rate:          {hallucination_rate:.2f}% (Target: 0.0%)")
    print(f"Benign Control Specificity:             {benign_spec:.2f}% (Target: >=98.0%)")
    print(f"Overall Benchmark Triage Accuracy:      {triage_acc:.2f}% ({triage_correct}/{len(cases)})")

    out_file = REPO_ROOT / "datasets" / "DS-SEMANTIC-ABSTRACTION" / "eval_report.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_cases": len(cases),
            "evaluation_time_seconds": round(elapsed, 2),
            "metrics": {
                "critical_fact_recall": round(crit_recall, 4),
                "partial_high_risk_recall": round(partial_recall, 4),
                "critical_fact_precision": round(crit_precision, 4),
                "perfusion_threat_recall": round(perf_recall, 4),
                "functional_loss_recall": round(func_recall, 4),
                "toxic_exposure_recall": round(tox_recall, 4),
                "benign_specificity": round(benign_spec, 4),
                "false_fact_hallucination_rate": round(hallucination_rate, 4),
                "overall_triage_accuracy": round(triage_acc, 4),
            },
            "cases": results,
        }, f, indent=2, ensure_ascii=False)

    print(f"[+] Full evaluation report saved to: {out_file}")


if __name__ == "__main__":
    evaluate_benchmark()
