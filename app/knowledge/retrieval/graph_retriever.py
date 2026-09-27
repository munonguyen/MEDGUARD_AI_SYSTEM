"""Knowledge Graph Traversal Retriever.

Identifies clinical entities in the query via ClinicalOntology, traverses
explicit ontological relations (interactions, contraindications, red-flag links),
and retrieves corresponding NormalizedEvidence items with top confidence.
"""

from __future__ import annotations

from typing import Any
from app.knowledge.graph.ontology import ClinicalOntology, default_ontology
from app.knowledge.ingestion.normalizer import NormalizedEvidence
from app.knowledge.ingestion.version_manager import KnowledgeSnapshot


class GraphRetriever:
    """Retrieves evidence backed by hard ontological relationships."""

    def __init__(self, ontology: ClinicalOntology = default_ontology) -> None:
        self.ontology = ontology
        self.snapshot: KnowledgeSnapshot | None = None

    def set_snapshot(self, snapshot: KnowledgeSnapshot) -> None:
        self.snapshot = snapshot

    def search(self, query: str, top_k: int = 10) -> list[tuple[NormalizedEvidence, float]]:
        """Resolves concepts in query and finds evidence directly coupled with graph relations."""
        if not self.snapshot:
            return []

        matched_concepts = self.ontology.resolve_all_concepts(query)
        if not matched_concepts:
            return []

        matched_evidence_ids: dict[str, float] = {}

        # 1. Multi-entity interaction checks (e.g. Warfarin + Ibuprofen)
        for i in range(len(matched_concepts)):
            for j in range(i + 1, len(matched_concepts)):
                e1, e2 = matched_concepts[i], matched_concepts[j]
                rels = self.ontology.query_relations(subject_id=e1, object_id=e2)
                rels.extend(self.ontology.query_relations(subject_id=e2, object_id=e1))
                for r in rels:
                    score = 1.0 if r.severity in ("major", "critical") else 0.85
                    # Find corresponding evidence in snapshot
                    for ev_id, ev in self.snapshot.evidence_items.items():
                        if ev.source_id == r.source_id or r.subject_id.split(".")[-1] in ev.concept:
                            matched_evidence_ids[ev_id] = max(matched_evidence_ids.get(ev_id, 0.0), score)

        # 2. Single-entity red flag and disease checks
        for cid in matched_concepts:
            rels = self.ontology.query_relations(subject_id=cid)
            for r in rels:
                score = 0.9 if r.predicate == "has_red_flag" else 0.75
                for ev_id, ev in self.snapshot.evidence_items.items():
                    if r.object_id.split(".")[-1] in ev.concept or r.subject_id.split(".")[-1] in ev.concept:
                        matched_evidence_ids[ev_id] = max(matched_evidence_ids.get(ev_id, 0.0), score)

        results: list[tuple[NormalizedEvidence, float]] = []
        for ev_id, score in matched_evidence_ids.items():
            ev = self.snapshot.get_evidence(ev_id)
            if ev:
                results.append((ev, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
