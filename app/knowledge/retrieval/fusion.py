"""Reciprocal Rank Fusion (RRF) Layer for Multi-Modal Retrieval."""

from __future__ import annotations

from typing import Any
from app.knowledge.ingestion.normalizer import NormalizedEvidence


def reciprocal_rank_fusion(
    ranked_runs: list[list[tuple[NormalizedEvidence, float]]],
    k: int = 60,
    top_n: int = 15,
) -> list[tuple[NormalizedEvidence, float]]:
    """Combines multiple ranked runs (e.g.

    BM25, Dense Vector, Knowledge Graph)
    using the standard formula: RRF(d) = sum(1 / (k + rank_i(d))).
    """
    rrf_scores: dict[str, float] = {}
    evidence_lookup: dict[str, NormalizedEvidence] = {}

    for run in ranked_runs:
        for rank, (ev, _) in enumerate(run, 1):
            evidence_lookup[ev.evidence_id] = ev
            rrf_scores[ev.evidence_id] = rrf_scores.get(ev.evidence_id, 0.0) + (1.0 / (k + rank))

    fused = [
        (evidence_lookup[ev_id], score)
        for ev_id, score in rrf_scores.items()
    ]
    fused.sort(key=lambda x: x[1], reverse=True)
    return fused[:top_n]
