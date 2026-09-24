"""MedGuard AI — Structured Replay Harness on Blind V7 Failures.

Implements the 3-mode replay methodology defined in the V8 Roadmap:
- Mode A: Raw text -> Fact Parser only (diagnostic of representation gap: missing vs partial)
- Mode B: Oracle-derived structured facts -> Downstream (proves whether failure is representation vs reasoning)
- Mode C: Minimal-fact ablation (identifies which specific clinical concept/fact decides triage)
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.models.clinical_events import (
    ClinicalAssertion,
    ClinicalEvent,
    ClinicalFactSet,
    OnsetTrajectory,
    SeverityLevel,
)
from app.services.clinical_fact_parser import parse_semantic_clinical_facts
from app.services.clinical_text import normalize_search_text
from app.services.clinical_threat_graph import evaluate_threat_graph, ThreatLevel
from app.services.compositional_reasoner import evaluate_compositional_risk
from app.services.triage_resolver import resolve_triage
from blind_v7.vault_crypto import load_sealed_vault


# Mapping oracle must_detect concepts to canonical ClinicalEvent archetypes
ORACLE_CONCEPT_ARCHETYPES: dict[str, dict[str, Any]] = {
    "circulatory_compromise": {
        "concept": "circulatory_compromise",
        "organ_system": "cardiovascular",
        "physiologic_consequence": "circulatory_compromise",
        "functional_loss": "loss_of_consciousness_or_perfusion",
        "severity": SeverityLevel.CRITICAL_EXTREME,
    },
    "organ_hypoperfusion": {
        "concept": "organ_hypoperfusion",
        "organ_system": "cardiovascular",
        "physiologic_consequence": "organ_hypoperfusion_or_necrosis",
        "functional_loss": "loss_of_consciousness_or_perfusion",
        "severity": SeverityLevel.CRITICAL_EXTREME,
    },
    "acute_tissue_ischemia": {
        "concept": "arterial_occlusion",
        "organ_system": "vascular",
        "physiologic_consequence": "limb_perfusion_failure",
        "functional_loss": "loss_of_limb_perfusion",
        "severity": SeverityLevel.CRITICAL_EXTREME,
    },
    "systemic_toxic_state": {
        "concept": "toxic_ingestion",
        "organ_system": "toxicology",
        "physiologic_consequence": "acute_toxic_metabolic_threat",
        "functional_loss": "loss_of_protective_reflexes",
        "severity": SeverityLevel.CRITICAL_EXTREME,
    },
    "perforation_risk": {
        "concept": "abdominal_rigidity",
        "organ_system": "abdomen",
        "physiologic_consequence": "peritoneal_irritation",
        "functional_loss": "inability_to_tolerate_palpation_movement",
        "severity": SeverityLevel.CRITICAL_EXTREME,
    },
    "major_barrier_failure": {
        "concept": "extensive_burn_injury",
        "organ_system": "dermatology",
        "physiologic_consequence": "organ_hypoperfusion_or_necrosis",
        "functional_loss": "loss_of_skin_barrier_integrity",
        "severity": SeverityLevel.CRITICAL_EXTREME,
    },
    "respiratory_failure": {
        "concept": "acute_respiratory_failure",
        "organ_system": "respiratory",
        "physiologic_consequence": "airway_compromise",
        "functional_loss": "inability_to_speak_full_sentences",
        "severity": SeverityLevel.CRITICAL_EXTREME,
    },
    "airway_obstruction": {
        "concept": "airway_obstruction_or_severe_dyspnea",
        "organ_system": "respiratory",
        "physiologic_consequence": "airway_compromise",
        "functional_loss": "inability_to_speak_full_sentences",
        "severity": SeverityLevel.CRITICAL_EXTREME,
    },
    "internal_hemorrhage": {
        "concept": "massive_hemorrhage",
        "organ_system": "cardiovascular",
        "physiologic_consequence": "internal_hemorrhage_and_shock",
        "functional_loss": "loss_of_hemodynamic_stability",
        "severity": SeverityLevel.CRITICAL_EXTREME,
    },
    "acute_neurologic_functional_loss": {
        "concept": "acute_stroke",
        "organ_system": "neurology",
        "physiologic_consequence": "acute_neurologic_deficit",
        "functional_loss": "loss_of_motor_power",
        "severity": SeverityLevel.CRITICAL_EXTREME,
    },
    "time_critical_organ_loss": {
        "concept": "vision_loss",
        "organ_system": "ophthalmology",
        "physiologic_consequence": "retinal_or_optic_ischemia",
        "functional_loss": "loss_of_sight",
        "severity": SeverityLevel.CRITICAL_EXTREME,
    },
    "metabolic_instability": {
        "concept": "diabetic_ketoacidosis",
        "organ_system": "metabolic",
        "physiologic_consequence": "metabolic_crisis",
        "functional_loss": "loss_of_acid_base_homeostasis",
        "severity": SeverityLevel.CRITICAL_EXTREME,
    },
}


def create_oracle_fact(concept_name: str) -> ClinicalEvent:
    meta = ORACLE_CONCEPT_ARCHETYPES.get(concept_name)
    if meta:
        return ClinicalEvent(
            concept=meta["concept"],
            organ_system=meta["organ_system"],
            physiologic_consequence=meta["physiologic_consequence"],
            functional_loss=meta["functional_loss"],
            severity=meta["severity"],
            onset=OnsetTrajectory.SUDDEN,
            assertion=ClinicalAssertion.PRESENT,
            temporality="current",
            experiencer="patient",
            evidence_span=concept_name,
        )
    return ClinicalEvent(
        concept=concept_name,
        organ_system="general",
        physiologic_consequence="organ_hypoperfusion_or_necrosis",
        functional_loss="general_functional_loss",
        severity=SeverityLevel.CRITICAL_EXTREME,
        onset=OnsetTrajectory.SUDDEN,
        assertion=ClinicalAssertion.PRESENT,
        temporality="current",
        experiencer="patient",
        evidence_span=concept_name,
    )


def run_mode_a(case: dict[str, Any], oracle_info: dict[str, Any]) -> dict[str, Any]:
    """Mode A: Raw text -> Fact Parser only."""
    messages = case.get("messages") or []
    raw_input = messages[-1]["content"] if messages else (case.get("input") or "")
    normalized = normalize_search_text(raw_input)

    fact_set = parse_semantic_clinical_facts(raw_input)

    events_extracted = [e.concept for e in fact_set.events]
    must_detect = oracle_info.get("must_detect", [])

    events_missed = []
    for md in must_detect:
        matched = False
        for e in fact_set.events:
            if (
                md in e.concept
                or (e.physiologic_consequence and md in e.physiologic_consequence)
                or (e.functional_loss and md in e.functional_loss)
            ):
                matched = True
                break
        if not matched:
            events_missed.append(md)

    evidence_spans = [e.evidence_span for e in fact_set.events if e.evidence_span]
    assertions = [e.assertion.value for e in fact_set.events]
    temporalities = [e.temporality for e in fact_set.events]
    experiencers = [e.experiencer for e in fact_set.events]
    functional_losses = [e.functional_loss for e in fact_set.events if e.functional_loss]
    physiologic_consequences = [e.physiologic_consequence for e in fact_set.events if e.physiologic_consequence]

    is_completely_blind = (len(events_extracted) == 0)
    is_partially_extracted = (len(events_extracted) > 0 and len(events_missed) > 0)
    is_fully_extracted = (len(must_detect) > 0 and len(events_missed) == 0)

    return {
        "raw_input": raw_input,
        "normalized_text": normalized,
        "events_extracted": events_extracted,
        "events_missed": events_missed,
        "evidence_spans": evidence_spans,
        "assertions": assertions,
        "temporalities": temporalities,
        "experiencers": experiencers,
        "functional_losses": functional_losses,
        "physiologic_consequences": physiologic_consequences,
        "diagnosis_state": "COMPLETELY_BLIND" if is_completely_blind else ("PARTIAL_EXTRACTION" if is_partially_extracted else "FULLY_EXTRACTED"),
    }


def run_mode_b(case: dict[str, Any], oracle_info: dict[str, Any]) -> dict[str, Any]:
    """Mode B: Oracle-derived structured facts -> Downstream."""
    must_detect = oracle_info.get("must_detect", [])
    expected_triage = oracle_info.get("oracle_triage", "EMERGENCY")
    if expected_triage == "T4":
        expected_triage = "EMERGENCY"

    oracle_events = [create_oracle_fact(md) for md in must_detect]
    if not oracle_events:
        # Fallback archetype for emergency cases without explicit must_detect list
        if expected_triage == "EMERGENCY":
            oracle_events = [create_oracle_fact("circulatory_compromise")]
        else:
            oracle_events = [ClinicalEvent(
                concept="mild_symptom",
                organ_system="general",
                severity=SeverityLevel.MODERATE,
                onset=OnsetTrajectory.GRADUAL,
                assertion=ClinicalAssertion.PRESENT,
                temporality="current",
                experiencer="patient",
            )]

    oracle_fact_set = ClinicalFactSet(
        raw_text=case.get("input", ""),
        normalized_text=normalize_search_text(case.get("input", "")),
        events=tuple(oracle_events),
        semantic_coverage=1.0,
    )

    comp_hyp = evaluate_compositional_risk(oracle_fact_set)
    has_functional_loss = oracle_fact_set.has_functional_loss([
        "loss_of_sight", "loss_of_motor_power", "inability_to_speak_full_sentences",
        "inability_to_tolerate_palpation_movement", "loss_of_limb_perfusion",
        "loss_of_consciousness_or_perfusion", "loss_of_skin_barrier_integrity",
    ])

    resolved = resolve_triage(
        rule_urgency=None,
        semantic_urgency=None,
        compositional_urgency=comp_hyp.disposition,
        compositional_confidence=comp_hyp.risk_confidence,
        semantic_status="UNDERSTOOD",
        fact_coverage=oracle_fact_set.semantic_coverage,
        has_acute_functional_loss=has_functional_loss,
    )

    downstream_urgency = resolved.urgency
    acceptable = oracle_info.get("acceptable_triage", [expected_triage])

    is_correct = (downstream_urgency in acceptable or downstream_urgency == expected_triage)

    return {
        "oracle_facts": [e.concept for e in oracle_events],
        "compositional_disposition": comp_hyp.disposition,
        "compositional_summary": comp_hyp.threat_summary,
        "downstream_urgency": downstream_urgency,
        "expected_triage": expected_triage,
        "downstream_correct": is_correct,
        "bottleneck_attribution": "REPRESENTATION_GAP" if is_correct else "REASONING_GAP",
    }


def run_mode_c(case: dict[str, Any], oracle_info: dict[str, Any]) -> dict[str, Any]:
    """Mode C: Minimal-fact ablation."""
    must_detect = oracle_info.get("must_detect", [])
    expected_triage = oracle_info.get("oracle_triage", "EMERGENCY")
    if expected_triage == "T4":
        expected_triage = "EMERGENCY"

    if not must_detect:
        return {"minimal_facts": [], "ablation_log": ["No distinct must_detect facts to ablate"]}

    oracle_events = [create_oracle_fact(md) for md in must_detect]
    acceptable = oracle_info.get("acceptable_triage", [expected_triage])

    ablation_log = []
    minimal_subsets = []

    # 1. Single fact tests
    for ev in oracle_events:
        test_fact_set = ClinicalFactSet(
            raw_text="ablation_test",
            normalized_text="ablation_test",
            events=(ev,),
            semantic_coverage=1.0,
        )
        comp_hyp = evaluate_compositional_risk(test_fact_set)
        has_fl = test_fact_set.has_functional_loss([
            "loss_of_sight", "loss_of_motor_power", "inability_to_speak_full_sentences",
            "inability_to_tolerate_palpation_movement", "loss_of_limb_perfusion",
            "loss_of_consciousness_or_perfusion", "loss_of_skin_barrier_integrity",
        ])
        res = resolve_triage(
            rule_urgency=None,
            semantic_urgency=None,
            compositional_urgency=comp_hyp.disposition,
            compositional_confidence=comp_hyp.risk_confidence,
            semantic_status="UNDERSTOOD",
            fact_coverage=1.0,
            has_acute_functional_loss=has_fl,
        )
        outcome = res.urgency
        success = (outcome in acceptable or outcome == expected_triage)
        ablation_log.append(f"[{ev.concept}] -> {outcome} ({'PASS' if success else 'FAIL'})")
        if success:
            minimal_subsets.append([ev.concept])

    # 2. Pairwise tests if no single fact passed and there are >= 2 facts
    if not minimal_subsets and len(oracle_events) >= 2:
        for i in range(len(oracle_events)):
            for j in range(i + 1, len(oracle_events)):
                pair = (oracle_events[i], oracle_events[j])
                test_fact_set = ClinicalFactSet(
                    raw_text="ablation_test",
                    normalized_text="ablation_test",
                    events=pair,
                    semantic_coverage=1.0,
                )
                comp_hyp = evaluate_compositional_risk(test_fact_set)
                has_fl = test_fact_set.has_functional_loss([
                    "loss_of_sight", "loss_of_motor_power", "inability_to_speak_full_sentences",
                    "inability_to_tolerate_palpation_movement", "loss_of_limb_perfusion",
                    "loss_of_consciousness_or_perfusion", "loss_of_skin_barrier_integrity",
                ])
                res = resolve_triage(
                    rule_urgency=None,
                    semantic_urgency=None,
                    compositional_urgency=comp_hyp.disposition,
                    compositional_confidence=comp_hyp.risk_confidence,
                    semantic_status="UNDERSTOOD",
                    fact_coverage=1.0,
                    has_acute_functional_loss=has_fl,
                )
                outcome = res.urgency
                success = (outcome in acceptable or outcome == expected_triage)
                pair_names = [ev.concept for ev in pair]
                ablation_log.append(f"{pair_names} -> {outcome} ({'PASS' if success else 'FAIL'})")
                if success:
                    minimal_subsets.append(pair_names)

    return {
        "minimal_subsets": minimal_subsets,
        "ablation_log": ablation_log,
    }


def main():
    report_file = REPO_ROOT / "blind_v7" / "baseline" / "final_report.json"
    cases_file = REPO_ROOT / "blind_v7" / "sealed_cases" / "cases.json"
    oracle_file = REPO_ROOT / "blind_v7" / "oracle_vault" / "oracle.enc"

    with open(report_file, "r", encoding="utf-8") as f:
        rep = json.load(f)
    failures = rep["part_d_root_cause_distribution"].get("failure_details", [])

    with open(cases_file, "r", encoding="utf-8") as f:
        raw_cases = json.load(f)
    case_map = {c["case_id"]: c for c in raw_cases}

    oracle_data = load_sealed_vault(oracle_file)
    oracle_map = {c["case_id"]: c for c in oracle_data["cases"]}

    print("=" * 80)
    print("MEDGUARD AI — V8 STRUCTURED REPLAY HARNESS ON 89 BLIND V7 FAILURES")
    print("=" * 80)
    print(f"Loaded {len(failures)} failures from Blind V7 baseline snapshot.")

    results = []
    mode_a_blind_count = 0
    mode_a_partial_count = 0
    mode_b_correct_count = 0
    mode_b_reasoning_gap_count = 0

    critical_decision_facts: dict[str, int] = {}

    for idx, fail in enumerate(failures, 1):
        cid = fail["case_id"]
        c_obj = case_map.get(cid, {})
        ora_obj = oracle_map.get(cid, {})

        res_a = run_mode_a(c_obj, ora_obj)
        res_b = run_mode_b(c_obj, ora_obj)
        res_c = run_mode_c(c_obj, ora_obj)

        if res_a["diagnosis_state"] == "COMPLETELY_BLIND":
            mode_a_blind_count += 1
        else:
            mode_a_partial_count += 1

        if res_b["downstream_correct"]:
            mode_b_correct_count += 1
        else:
            mode_b_reasoning_gap_count += 1

        for subset in res_c.get("minimal_subsets", []):
            for fact in subset:
                critical_decision_facts[fact] = critical_decision_facts.get(fact, 0) + 1

        results.append({
            "case_id": cid,
            "cohort": ora_obj.get("cohort", "unknown"),
            "oracle_triage": ora_obj.get("oracle_triage"),
            "actual_v7_triage": fail.get("actual"),
            "mode_a": res_a,
            "mode_b": res_b,
            "mode_c": res_c,
        })

    # Summary Statistics
    print("\n" + "-" * 80)
    print("STRUCTURED REPLAY QUANTITATIVE FINDINGS")
    print("-" * 80)
    print(f"Total Failures Replayed: {len(failures)}")
    print(f"\n[MODE A: Fact Parser Diagnostic]")
    print(f"  - Completely Blind (0 clinical events extracted):  {mode_a_blind_count} / {len(failures)} ({mode_a_blind_count/len(failures)*100:.1f}%)")
    print(f"  - Partial Extraction (extracted events missed key): {mode_a_partial_count} / {len(failures)} ({mode_a_partial_count/len(failures)*100:.1f}%)")

    print(f"\n[MODE B: Oracle-Derived Facts -> Downstream]")
    print(f"  - Resolved Correctly by Downstream (Representation Gap): {mode_b_correct_count} / {len(failures)} ({mode_b_correct_count/len(failures)*100:.1f}%)")
    print(f"  - Still Failed by Downstream (True Reasoning Gap):       {mode_b_reasoning_gap_count} / {len(failures)} ({mode_b_reasoning_gap_count/len(failures)*100:.1f}%)")

    print(f"\n[MODE C: Minimal Load-Bearing Decision Facts]")
    for fact, cnt in sorted(critical_decision_facts.items(), key=lambda x: -x[1]):
        print(f"  - {fact:35s}: load-bearing in {cnt} failure cases")

    # Write full replay report to disk
    out_path = REPO_ROOT / "blind_v7" / "replay_89_failures_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_failures": len(failures),
            "mode_a_summary": {
                "completely_blind": mode_a_blind_count,
                "partial_extraction": mode_a_partial_count,
            },
            "mode_b_summary": {
                "downstream_correct_representation_gap": mode_b_correct_count,
                "downstream_failed_reasoning_gap": mode_b_reasoning_gap_count,
            },
            "critical_decision_facts": critical_decision_facts,
            "replayed_cases": results,
        }, f, indent=2, ensure_ascii=False)
    print(f"\n[+] Full structured replay artifact saved to: {out_path}")


if __name__ == "__main__":
    main()
