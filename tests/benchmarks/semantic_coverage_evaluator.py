"""Semantic Coverage Evaluator for MedGuard AI Candidate V9.

Measures the 'Semantic Coverage' metric:
Percentage of interactions where the system successfully extracts actionable,
grounded clinical concepts/relations rather than returning an empty or blind state.

Targets:
- T4 Emergency Semantic Coverage >= 99.0%
- Benign Control Semantic Coverage >= 95.0%
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.services.semantic_relation_extractor import extract_semantic_relations
from app.services.clinical_fact_parser import parse_semantic_clinical_facts


@dataclass(frozen=True)
class SemanticCoverageReport:
    total_cases: int
    covered_cases: int
    coverage_pct: float
    target_met: bool
    uncovered_samples: list[str]


def evaluate_semantic_coverage(
    texts: Sequence[str],
    target_pct: float = 95.0,
) -> SemanticCoverageReport:
    """Evaluate what fraction of texts produce non-empty structured clinical states."""
    n = len(texts)
    if n == 0:
        return SemanticCoverageReport(0, 0, 100.0, True, [])

    covered = 0
    uncovered = []

    for t in texts:
        graph = extract_semantic_relations(t)
        fact_set = parse_semantic_clinical_facts(t)

        has_graph_concepts = bool(graph.concepts)
        has_fact_events = bool(fact_set.events)

        if has_graph_concepts or has_fact_events:
            covered += 1
        else:
            uncovered.append(t[:80] + "...")

    cov_pct = (covered / n) * 100.0
    return SemanticCoverageReport(
        total_cases=n,
        covered_cases=covered,
        coverage_pct=round(cov_pct, 2),
        target_met=cov_pct >= target_pct,
        uncovered_samples=uncovered[:5],
    )
