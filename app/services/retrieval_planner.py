"""Intelligent Query-driven Retrieval Planner.

Inspects user intent and clinical concepts to select the optimal combination of
retrieval engines (BM25, Dense Vector, Knowledge Graph, Legal index) rather
than blindly running all engines for every request.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from app.knowledge.graph.ontology import ClinicalOntology, default_ontology


class RetrievalPlan(BaseModel):
    """Selective dispatch configuration for multi-modal retrieval."""
    use_bm25: bool = True
    use_vector: bool = True
    use_graph: bool = False
    use_legal: bool = False
    target_domains: list[str] = Field(default_factory=list)
    plan_explanation: str = ""


class RetrievalPlanner:
    """Decides retrieval engine orchestration based on query features."""

    def __init__(self, ontology: ClinicalOntology = default_ontology) -> None:
        self.ontology = ontology

    def plan(self, query: str) -> RetrievalPlan:
        q_lower = query.lower()
        matched_concepts = self.ontology.resolve_all_concepts(query)

        has_drug = any("drug." in cid for cid in matched_concepts) or any(k in q_lower for k in ("thuốc", "uống", "liều", "phối hợp", "dược"))
        has_legal = any(k in q_lower for k in ("luật", "quy định", "bộ y tế ban hành", "nghị định", "thông tư", "pháp lý", "chứng chỉ"))
        has_emergency = any(k in q_lower for k in ("cấp cứu", "115", "đột ngột", "nguy kịch", "bất tỉnh", "thở rít"))

        # Specialized Legal Queries
        if has_legal and not has_emergency and not has_drug:
            return RetrievalPlan(
                use_bm25=True,
                use_vector=True,
                use_graph=False,
                use_legal=True,
                target_domains=["legal_regulation"],
                plan_explanation="Legal and regulatory compliance query routed to BM25 and legal guidelines.",
            )

        # Specialized Pharmacology & Interaction Queries
        if has_drug:
            return RetrievalPlan(
                use_bm25=True,
                use_vector=True,
                use_graph=True,
                use_legal=False,
                target_domains=["drug_monograph", "pharmacology", "clinical_guideline"],
                plan_explanation="Medication and interaction query activated Knowledge Graph traversal alongside BM25 exact match.",
            )

        # General Clinical / Symptom Queries
        return RetrievalPlan(
            use_bm25=True,
            use_vector=True,
            use_graph=bool(matched_concepts),
            use_legal=False,
            target_domains=["clinical_guideline", "emergency_protocol"],
            plan_explanation="Clinical symptom presentation routed to hybrid BM25 and semantic vector with concept graph enrichment.",
        )
