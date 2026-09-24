"""Root-cause trace and diagnostic analysis for remaining 60 Pure-T4 V8 misses and 42 FPs."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blind_v8.vault_crypto import load_sealed_vault as load_sealed_vault_v8
from scripts.run_historical_regression_2100 import load_v8_cases, load_all_2100_cases
from scripts.run_1800_regression import evaluate_single_case
from app.services.semantic_relation_extractor import extract_semantic_relations
from app.services.semantic_abstraction_lattice import evaluate_abstraction_lattice
from app.services.evidence_strength_scorer import score_evidence_strength
from app.services.toxicology_signature_router import route_by_toxicity_signature
from app.services.clinical_fact_parser import parse_semantic_clinical_facts
from app.services.clinical_threat_graph import evaluate_threat_graph, ThreatLevel
from app.services.rules import triage_rules


def run_v8_diagnostics():
    print("=" * 85)
    print("ANALYZING V8 PURE-T4 PERFORMANCE UNDER CANDIDATE V9")
    print("=" * 85)

    v8_cases = load_v8_cases()
    pure_t4_v8 = [c for c in v8_cases if c.expected_triage == "EMERGENCY" and (c.acceptable_triages == ["EMERGENCY"] or not c.acceptable_triages)]

    print(f"Total V8 Pure T4 Cases: {len(pure_t4_v8)}")

    # Load baseline V8 predictions to identify which 33 were rescued
    v8_pred_file = REPO_ROOT / "blind_v8" / "outputs" / "predictions.jsonl"
    baseline_predictions = {}
    if v8_pred_file.exists():
        with open(v8_pred_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    p = json.loads(line)
                    baseline_predictions[p["case_id"]] = p["final_triage"]

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(evaluate_single_case, c, "diag") for c in pure_t4_v8]
        v9_results = [(c, f.result()) for c, f in zip(pure_t4_v8, futures)]

    caught = []
    missed_urgent = []
    missed_routine = []
    rescued = []

    for c, r in v9_results:
        act = r["actual_triage"]
        cid = c.case_id
        base_act = baseline_predictions.get(cid, "UNKNOWN")

        if act == "EMERGENCY":
            caught.append((c, r))
            if base_act != "EMERGENCY":
                rescued.append((c, r))
        elif act == "URGENT":
            missed_urgent.append((c, r))
        else:
            missed_routine.append((c, r))

    all_missed = missed_urgent + missed_routine

    print(f"Caught:            {len(caught)} (Rescued from V8 baseline: {len(rescued)})")
    print(f"Missed (URGENT):   {len(missed_urgent)}")
    print(f"Missed (ROUTINE):  {len(missed_routine)}")
    print(f"Total Missed:      {len(all_missed)}")
    print("-" * 85)

    # Detailed trace of the 60 missed cases
    miss_traces = []
    bucket_counts = {
        "R1_fact_miss": 0,
        "R2_relation_miss": 0,
        "R3_abstraction_lattice_gap": 0,
        "R4_singleton_misclassification": 0,
        "R5_partial_evidence_issue": 0,
        "R6_toxicology_miss": 0,
        "R7_threat_activation_miss": 0,
        "R8_gate_integration_issue": 0,
        "R9_oracle_issue": 0,
    }

    for c, r in all_missed:
        txt = c.input_text
        graph = extract_semantic_relations(txt)
        lattice = evaluate_abstraction_lattice(graph)
        sgt = score_evidence_strength(txt)
        tox = route_by_toxicity_signature(txt)
        fact_set = parse_semantic_clinical_facts(graph.normalized_text)
        threat = evaluate_threat_graph(fact_set)
        rule_eval = triage_rules(txt)

        # Attribution logic
        assigned_bucket = "R3_abstraction_lattice_gap"
        if len(graph.concepts) == 0 and len(tox.matched_dimensions) == 0:
            assigned_bucket = "R1_fact_miss"
        elif tox.is_toxicology_eligible and not tox.is_emergency_toxidrome:
            assigned_bucket = "R6_toxicology_miss"
        elif sgt.tier.value == "WEAK_SINGLETON" and "trieu chung" in txt:
            assigned_bucket = "R4_singleton_misclassification"
        elif len(graph.concepts) >= 1 and not lattice.has_emergency_threat:
            assigned_bucket = "R3_abstraction_lattice_gap"
        elif lattice.has_emergency_threat and r["actual_triage"] != "EMERGENCY":
            assigned_bucket = "R8_gate_integration_issue"
        elif threat.has_threat_at_least(ThreatLevel.HIGH) and r["actual_triage"] != "EMERGENCY":
            assigned_bucket = "R7_threat_activation_miss"

        bucket_counts[assigned_bucket] += 1

        trace = {
            "case_id": c.case_id,
            "cohort": c.cohort,
            "raw_input": txt,
            "actual_triage": r["actual_triage"],
            "assigned_root_cause": assigned_bucket,
            "fact_extraction": list(graph.concepts.keys()),
            "semantic_relations": [f"{rel.source_concept}->{rel.target_concept}" for rel in graph.relations],
            "abstraction_lattice": [p.archetype.value for p in lattice.active_archetypes],
            "has_lattice_emergency": lattice.has_emergency_threat,
            "singleton_tier": sgt.tier.value,
            "singleton_floor": sgt.recommended_floor,
            "tox_eligible": tox.is_toxicology_eligible,
            "tox_emergency": tox.is_emergency_toxidrome,
            "tox_syndrome": tox.suspected_syndrome,
            "threat_active": threat.critical_dimensions + threat.high_dimensions,
            "rule_flags": rule_eval.red_flags,
            "rule_ids": rule_eval.rule_ids,
        }
        miss_traces.append(trace)

    print("\nROOT-CAUSE DISTRIBUTION OF 60 MISSED CASES:")
    for b, count in bucket_counts.items():
        pct = (count / len(all_missed)) * 100.0 if all_missed else 0.0
        print(f"  - {b:<32}: {count:2d} ({pct:5.1f}%)")

    # Save detailed miss report
    out_miss_file = REPO_ROOT / "outputs" / "v8_60_misses_detailed_trace.json"
    with open(out_miss_file, "w", encoding="utf-8") as f:
        json.dump(miss_traces, f, indent=2, ensure_ascii=False)
    print(f"\n[+] Saved 60-miss trace to: {out_miss_file}")

    # Comparative analysis: 33 Rescued vs 60 Missed
    print("\n" + "=" * 85)
    print("COMPARATIVE FEATURE ANALYSIS: 33 RESCUED VS 60 MISSED")
    print("=" * 85)

    rescued_facts = []
    missed_facts = []
    rescued_relations = []
    missed_relations = []
    rescued_lat_active = 0
    missed_lat_active = 0
    rescued_tox_active = 0
    missed_tox_active = 0
    rescued_sgt_critical = 0
    missed_sgt_critical = 0

    for c, r in rescued:
        g = extract_semantic_relations(c.input_text)
        lat = evaluate_abstraction_lattice(g)
        t = route_by_toxicity_signature(c.input_text)
        s = score_evidence_strength(c.input_text)
        rescued_facts.append(len(g.concepts))
        rescued_relations.append(len(g.relations))
        if lat.has_emergency_threat: rescued_lat_active += 1
        if t.is_emergency_toxidrome or t.is_toxicology_eligible: rescued_tox_active += 1
        if s.tier.value == "CRITICAL_SINGLETON": rescued_sgt_critical += 1

    for c, r in all_missed:
        g = extract_semantic_relations(c.input_text)
        lat = evaluate_abstraction_lattice(g)
        t = route_by_toxicity_signature(c.input_text)
        s = score_evidence_strength(c.input_text)
        missed_facts.append(len(g.concepts))
        missed_relations.append(len(g.relations))
        if lat.has_emergency_threat: missed_lat_active += 1
        if t.is_emergency_toxidrome or t.is_toxicology_eligible: missed_tox_active += 1
        if s.tier.value == "CRITICAL_SINGLETON": missed_sgt_critical += 1

    avg_rescued_facts = sum(rescued_facts) / len(rescued) if rescued else 0
    avg_missed_facts = sum(missed_facts) / len(all_missed) if all_missed else 0
    avg_rescued_rels = sum(rescued_relations) / len(rescued) if rescued else 0
    avg_missed_rels = sum(missed_relations) / len(all_missed) if all_missed else 0

    print(f"Feature                          | 33 Rescued Cases     | 60 Missed Cases")
    print(f"---------------------------------|----------------------|----------------------")
    print(f"Avg Extracted Concepts / Case    | {avg_rescued_facts:20.2f} | {avg_missed_facts:20.2f}")
    print(f"Avg Clinical Relations / Case    | {avg_rescued_rels:20.2f} | {avg_missed_rels:20.2f}")
    print(f"Abstraction Lattice Active       | {rescued_lat_active:13d} ({rescued_lat_active/len(rescued)*100:4.1f}%) | {missed_lat_active:13d} ({missed_lat_active/len(all_missed)*100:4.1f}%)")
    print(f"Toxicology Active                | {rescued_tox_active:13d} ({rescued_tox_active/len(rescued)*100:4.1f}%) | {missed_tox_active:13d} ({missed_tox_active/len(all_missed)*100:4.1f}%)")
    print(f"Critical Singleton Triggered     | {rescued_sgt_critical:13d} ({rescued_sgt_critical/len(rescued)*100:4.1f}%) | {missed_sgt_critical:13d} ({missed_sgt_critical/len(all_missed)*100:4.1f}%)")


def analyze_42_false_positives():
    print("\n" + "=" * 85)
    print("ANALYSIS OF 42 FALSE POSITIVES IN 2,100 HISTORICAL REGRESSION")
    print("=" * 85)

    cases = load_all_2100_cases()
    non_em_cases = [c for c in cases if c.expected_triage != "EMERGENCY"]
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(evaluate_single_case, c, "fp_diag") for c in non_em_cases]
        results = [f.result() for f in futures]

    fps = []
    for c, r in zip(non_em_cases, results):
        if r["actual_triage"] == "EMERGENCY":
            fps.append((c, r))

    print(f"Total False Positives Found: {len(fps)}")
    suite_fp = {}
    cluster_fp = {}

    fp_records = []
    for c, r in fps:
        suite = c.source_suite
        suite_fp[suite] = suite_fp.get(suite, 0) + 1

        # Check why it escalated to emergency
        txt = c.input_text
        rule_eval = triage_rules(txt)
        reason = ", ".join(rule_eval.red_flags) + " | " + ", ".join(rule_eval.rule_ids) + " | " + rule_eval.advice[:100]

        # Classify escalation mechanism
        mech = "Unknown"
        if "Phase 0a" in reason or "singleton" in reason.lower():
            mech = "Phase 0a (Singleton Escalation)"
        elif "Phase 0b" in reason or "toxicology" in reason.lower() or "độc" in reason.lower():
            mech = "Phase 0b (Toxicology Router)"
        elif "Phase 0" in reason or "Lattice" in reason or "sinh lý" in reason.lower():
            mech = "Phase 0c/1 (Abstraction Lattice)"
        elif "Phase 1" in reason or "threat" in reason.lower():
            mech = "Phase 1 (Clinical Threat Graph)"
        elif "Phase 2" in reason or "red_line" in reason.lower():
            mech = "Phase 2 (Deterministic Red Lines)"
        else:
            mech = f"Other ({reason[:30]})"

        cluster_fp[mech] = cluster_fp.get(mech, 0) + 1
        fp_records.append({
            "case_id": c.case_id,
            "suite": suite,
            "expected_triage": c.expected_triage,
            "input_text": txt,
            "escalation_mechanism": mech,
            "clinical_reasoning": reason,
        })

    print("\nFP Distribution by Suite:")
    for s, count in sorted(suite_fp.items()):
        print(f"  - {s}: {count} FPs")

    print("\nFP Systematic Escalation Mechanisms:")
    for m, count in sorted(cluster_fp.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {m:<35}: {count:2d} FPs")

    out_fp_file = REPO_ROOT / "outputs" / "historical_42_fps_trace.json"
    with open(out_fp_file, "w", encoding="utf-8") as f:
        json.dump(fp_records, f, indent=2, ensure_ascii=False)
    print(f"\n[+] Saved 42-FP trace to: {out_fp_file}")


if __name__ == "__main__":
    run_v8_diagnostics()
    analyze_42_false_positives()
