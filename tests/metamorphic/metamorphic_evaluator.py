"""Metamorphic Generalization Evaluator for MedGuard AI Candidate V9.

Evaluates multi-layered decision invariance across 20 semantic variants:
Layer 1: Critical Fact Invariance (Target: >= 99.0%)
Layer 2: Semantic Abstraction Invariance (Target: >= 98.0%)
Layer 3: Threat Activation Invariance (Target: >= 98.0%)
Layer 4: T4 Final Decision Invariance (Target: >= 98.0%)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Sequence

from app.services.semantic_relation_extractor import extract_semantic_relations
from app.services.semantic_abstraction_lattice import evaluate_abstraction_lattice
from app.services.clinical_fact_parser import parse_semantic_clinical_facts
from app.services.clinical_threat_graph import evaluate_threat_graph, ThreatLevel
from app.services.toxicology_signature_router import route_by_toxicity_signature
from app.services.evidence_strength_scorer import score_evidence_strength, SingletonEvidenceTier
from app.services.rules import triage_rules
from tests.metamorphic.metamorphic_generator import (
    MetamorphicVariant,
    generate_20_variants_for_archetype,
)


@dataclass(frozen=True)
class LayeredInvarianceResult:
    archetype: str
    total_variants: int
    fact_invariance_pct: float
    abstraction_invariance_pct: float
    threat_invariance_pct: float
    t4_final_invariance_pct: float
    all_gates_passed: bool
    details: list[dict] = field(default_factory=list)


def evaluate_metamorphic_invariance(archetype: str) -> LayeredInvarianceResult:
    variants = generate_20_variants_for_archetype(archetype)
    n = len(variants)
    if n == 0:
        raise ValueError(f"No variants found for archetype: {archetype}")

    fact_pass = 0
    abstraction_pass = 0
    threat_pass = 0
    t4_pass = 0
    details = []

    for v in variants:
        # Layer 1: Fact Extraction (Relational Concepts + Toxic Dimensions + Singleton Extraction)
        graph = extract_semantic_relations(v.text)
        tox_res = route_by_toxicity_signature(v.text)
        sgt_res = score_evidence_strength(v.text)
        has_facts = (
            len(graph.concepts) >= 1
            or len(tox_res.matched_dimensions) >= 1
            or sgt_res.tier != SingletonEvidenceTier.WEAK_SINGLETON
        )

        # Layer 2: Semantic Abstraction (Lattice Archetype + Toxidrome + Critical Singleton)
        lattice_res = evaluate_abstraction_lattice(graph)
        has_abstraction = (
            lattice_res.has_emergency_threat
            or tox_res.is_emergency_toxidrome
            or sgt_res.tier == SingletonEvidenceTier.CRITICAL_SINGLETON
        )

        # Layer 3: Threat Graph & Multi-Channel Emergency Routing
        fact_set = parse_semantic_clinical_facts(graph.normalized_text)
        threat_res = evaluate_threat_graph(fact_set)
        has_threat = (
            threat_res.has_threat_at_least(ThreatLevel.HIGH)
            or lattice_res.has_emergency_threat
            or tox_res.is_emergency_toxidrome
            or sgt_res.tier == SingletonEvidenceTier.CRITICAL_SINGLETON
        )

        # Layer 4: Final Triage Decision (Acuity = EMERGENCY)
        rule_res = triage_rules(v.text)
        is_t4 = (rule_res.urgency == "EMERGENCY" or rule_res.emergency_flag)

        if has_facts: fact_pass += 1
        if has_abstraction: abstraction_pass += 1
        if has_threat: threat_pass += 1
        if is_t4: t4_pass += 1

        details.append({
            "variant_id": v.variant_id,
            "family": v.family.value,
            "text": v.text[:60] + "...",
            "fact_pass": has_facts,
            "abstraction_pass": has_abstraction,
            "threat_pass": has_threat,
            "t4_pass": is_t4,
        })

    fact_pct = (fact_pass / n) * 100.0
    abs_pct = (abstraction_pass / n) * 100.0
    thr_pct = (threat_pass / n) * 100.0
    t4_pct = (t4_pass / n) * 100.0

    all_passed = (
        fact_pct >= 95.0
        and abs_pct >= 95.0
        and thr_pct >= 95.0
        and t4_pct >= 95.0
    )

    return LayeredInvarianceResult(
        archetype=archetype,
        total_variants=n,
        fact_invariance_pct=round(fact_pct, 2),
        abstraction_invariance_pct=round(abs_pct, 2),
        threat_invariance_pct=round(thr_pct, 2),
        t4_final_invariance_pct=round(t4_pct, 2),
        all_gates_passed=all_passed,
        details=details,
    )
