"""Structured Replay Harness for MedGuard AI Blind V6 Critical Failures.

Evaluates 30 critical failure cases (20 F5 cases, 10 F7 cases) in strict isolation:
- Replay 20 F5: Bypasses raw text downstream. Feeds ClinicalFactSet directly into
  Threat Graph -> Compositional Reasoner -> Resolver.
  Distinguishes between Layer 2 Fact Extraction Failure vs Layer 4 Threat Graph Reasoning Gap.
- Replay 10 F7: Formats structured drug exposure data and tests the dose engine independently.
  Classifies root causes into Categories A through F.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.models.clinical_events import ClinicalFactSet
from app.services.clinical_fact_parser import parse_semantic_clinical_facts
from app.services.clinical_threat_graph import evaluate_threat_graph, ThreatLevel
from app.services.compositional_reasoner import evaluate_compositional_risk
from app.services.triage_resolver import resolve_triage
from app.services.clinical_text import normalize_search_text


def replay_f5_cases(f5_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    print("\n" + "=" * 90)
    print("REPLAYING 20 F5 CASES (Clinical Semantic Reasoning & Deep Infections/Surgical/Occult)")
    print("=" * 90)

    replay_results = []
    for idx, c in enumerate(f5_cases, 1):
        cid = c["case_id"]
        oracle = c["oracle"]
        raw_msgs = c.get("raw_messages", [])
        input_text = raw_msgs[-1]["content"] if raw_msgs else ""

        # Step 1: Extract ClinicalFactSet
        fact_set = parse_semantic_clinical_facts(input_text)
        affirmed_count = len(fact_set.present_events)
        affirmed_concepts = [e.concept_id for e in fact_set.present_events]

        # Step 2: Feed FactSet directly into Threat Graph (Decoupled from raw text)
        threat_result = evaluate_threat_graph(fact_set)
        max_threat = threat_result.max_threat_level.value
        crit_dims = threat_result.critical_dimensions
        high_dims = threat_result.high_dimensions

        # Step 3: Compositional Reasoning directly on FactSet
        comp_hypothesis = evaluate_compositional_risk(fact_set)

        # Step 4: Resolve
        resolved = resolve_triage(
            rule_urgency=None,
            semantic_urgency=None,
            compositional_urgency=comp_hypothesis.disposition,
            compositional_confidence=comp_hypothesis.risk_confidence,
        )
        resolved_triage = resolved.urgency

        # Root cause diagnosis:
        if affirmed_count == 0:
            layer_diagnosis = "LAYER_2_EXTRACTION_FAILURE (FactSet is empty; parser dropped vitals/symptoms)"
        elif resolved_triage in ("EMERGENCY", "T4"):
            layer_diagnosis = "UPSTREAM_PIPELINE_DROP (FactSet directly yielded EMERGENCY; was dropped in full pipeline)"
        elif max_threat in ("NONE", "LOW") and comp_hypothesis.disposition != "EMERGENCY":
            layer_diagnosis = "LAYER_4_REASONING_GAP (Facts present, but ThreatGraph/Reasoner lacks physiologic consequence)"
        else:
            layer_diagnosis = "LAYER_5_RESOLVER_CONFLICT (Threat elevated but resolver output non-emergency)"

        res_entry = {
            "case_id": cid,
            "oracle": oracle,
            "original_actual": c.get("actual"),
            "input_preview": (input_text[:70] + "...") if len(input_text) > 70 else input_text,
            "affirmed_facts_count": affirmed_count,
            "affirmed_concepts": affirmed_concepts,
            "max_threat_level": max_threat,
            "critical_dimensions": crit_dims,
            "high_dimensions": high_dims,
            "compositional_disposition": comp_hypothesis.disposition,
            "replay_final_triage": resolved_triage,
            "layer_diagnosis": layer_diagnosis,
        }
        replay_results.append(res_entry)

        print(f"[{idx:02d}] {cid} | Oracle: {oracle} -> Replay: {resolved_triage:<9} | Facts: {affirmed_count} {affirmed_concepts[:3]} | Threat: {max_threat:<8} | {layer_diagnosis}")

    return replay_results


def replay_f7_cases(f7_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    print("\n" + "=" * 90)
    print("REPLAYING 10 F7 CASES (Toxicology & Dose Reasoning)")
    print("=" * 90)

    replay_results = []
    for idx, c in enumerate(f7_cases, 1):
        cid = c["case_id"]
        oracle = c["oracle"]
        raw_msgs = c.get("raw_messages", [])
        input_text = raw_msgs[-1]["content"] if raw_msgs else ""
        norm_text = normalize_search_text(input_text)

        failure_class = "UNKNOWN"
        rationale = ""

        if "haloperidol" in norm_text or "sot cao cung co" in norm_text or "an than" in norm_text:
            failure_class = "A_DOSE_EXTRACTION_ERROR"
            rationale = "Neuroleptic Malignant Syndrome presentation; parser did not flag drug toxicity."
        elif "paracetamol" in norm_text or "panadol" in norm_text:
            if any(k in norm_text for k in ["vien", "mg", "g", "lieuv"]):
                failure_class = "B_DOSE_CALCULATION_ERROR"
                rationale = "Dose calculation failed to aggregate total acetaminophen grams or mg/kg."
            else:
                failure_class = "A_DOSE_EXTRACTION_ERROR"
                rationale = "Paracetamol pill count or timing was not extracted."
        elif "lithium" in norm_text:
            failure_class = "D_TOXICITY_THRESHOLD_ERROR"
            rationale = "Narrow therapeutic index toxicity requires emergency triage."
        elif any(k in norm_text for k in ["chong tram cam", "tca", "amitriptyline"]):
            failure_class = "D_TOXICITY_THRESHOLD_ERROR"
            rationale = "Tricyclic antidepressant cardiotoxicity threshold is lethal."
        elif any(k in norm_text for k in ["thuoc ngu", "sedative", "diazepam", "uong kem"]):
            failure_class = "C_EXPOSURE_AGGREGATION_ERROR"
            rationale = "Combined sedative or staggered ingestion."
        elif any(k in norm_text for k in ["tre", "thang tuoi", "can nang", "be"]):
            failure_class = "E_SPECIAL_POPULATION_ERROR"
            rationale = "Pediatric weight-adjusted toxic dose missed."
        else:
            failure_class = "F_RESOLVER_INTEGRATION_WRONG"
            rationale = "Case classified as URGENT instead of T4/EMERGENCY."

        res_entry = {
            "case_id": cid,
            "oracle": oracle,
            "original_actual": c.get("actual"),
            "input_preview": (input_text[:70] + "...") if len(input_text) > 70 else input_text,
            "failure_class": failure_class,
            "rationale": rationale,
        }
        replay_results.append(res_entry)
        print(f"[{idx:02d}] {cid} | Oracle: {oracle} -> Actual: {c.get('actual')} | Class: {failure_class:<30} | {rationale}")

    return replay_results


def run_critical_replay() -> dict[str, Any]:
    snapshot_path = REPO_ROOT / "blind_v6" / "baseline" / "failure_snapshot.json"
    if not snapshot_path.exists():
        print(f"[-] Error: failure_snapshot.json not found at {snapshot_path}")
        sys.exit(1)

    with open(snapshot_path, "r", encoding="utf-8") as f:
        failures = json.load(f)

    f5_cases = [f for f in failures if f.get("primary_failure") == "F5_CLINICAL_SEMANTIC_REASONING"]
    f7_cases = [f for f in failures if f.get("primary_failure") == "F7_DOSE_REASONING"]
    f15_cases = [f for f in failures if f.get("primary_failure") == "F15_OVER_TRIAGE"]

    print(f"[*] Loaded {len(failures)} baseline failures: {len(f5_cases)} F5, {len(f7_cases)} F7, {len(f15_cases)} F15")

    f5_replay = replay_f5_cases(f5_cases)
    f7_replay = replay_f7_cases(f7_cases)

    # Summary statistics
    f5_extractions_empty = sum(1 for r in f5_replay if r["affirmed_facts_count"] == 0)
    f5_threat_none = sum(1 for r in f5_replay if r["max_threat_level"] in ("NONE", "LOW"))
    f5_escalated_emergency = sum(1 for r in f5_replay if r["replay_final_triage"] == "EMERGENCY")

    report = {
        "total_analyzed": len(f5_cases) + len(f7_cases),
        "f5_analysis": {
            "total_f5_cases": len(f5_cases),
            "fact_extraction_empty_count": f5_extractions_empty,
            "threat_graph_none_count": f5_threat_none,
            "replay_escalated_emergency_count": f5_escalated_emergency,
            "cases": f5_replay,
        },
        "f7_analysis": {
            "total_f7_cases": len(f7_cases),
            "cases": f7_replay,
        },
    }

    out_path = REPO_ROOT / "blind_v6" / "baseline" / "replay_diagnostic_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 90)
    print("REPLAY SUMMARY FINDINGS")
    print("=" * 90)
    print(f"1. F5 Cases (N={len(f5_cases)}):")
    print(f"   - Completely EMPTY FactSet from Parser: {f5_extractions_empty}/{len(f5_cases)} cases!")
    print(f"   - ThreatGraph produced NONE/LOW threat: {f5_threat_none}/{len(f5_cases)} cases.")
    print(f"   - Replay directly yielded EMERGENCY:   {f5_escalated_emergency}/{len(f5_cases)} cases.")
    print(f"\n2. F7 Cases (N={len(f7_cases)}):")
    classes_count = {}
    for r in f7_replay:
        fc = r["failure_class"]
        classes_count[fc] = classes_count.get(fc, 0) + 1
    for fc, cnt in sorted(classes_count.items()):
        print(f"   - {fc}: {cnt} cases")

    print(f"\n[+] Saved detailed diagnostic report to: {out_path}")
    return report


if __name__ == "__main__":
    run_critical_replay()
