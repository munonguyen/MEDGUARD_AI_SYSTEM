"""Multi-Factor Clinical Reranker.

Reranks candidate evidence based on multidimensional medical criteria:
- Semantic Relevance (40%)
- Issuing Authority Weight (25%)
- Clinical Safety / Risk Priority (15%)
- Guideline Freshness (10%)
- National Jurisdiction Match (10%)
"""

from __future__ import annotations

from typing import Any
from app.knowledge.ingestion.normalizer import NormalizedEvidence
from app.knowledge.provenance.source_registry import SourceRegistry, default_source_registry


class MultiFactorClinicalReranker:
    """Clinical Reranker optimizing safety, authority, and domestic jurisdiction."""

    def __init__(self, registry: SourceRegistry = default_source_registry) -> None:
        self.registry = registry

    def rerank(
        self,
        candidates: list[tuple[NormalizedEvidence, float]],
        query: str,
        user_jurisdiction: str = "VN",
        top_n: int = 7,
    ) -> list[tuple[NormalizedEvidence, float]]:
        if not candidates:
            return []

        # Find max similarity for normalization
        max_rel = max((score for _, score in candidates), default=1.0)
        if max_rel <= 0.0:
            max_rel = 1.0

        reranked: list[tuple[NormalizedEvidence, float]] = []

        is_emergency_query = any(k in query.lower() for k in ("cấp cứu", "115", "nguy kịch", "tức ngực", "méo miệng", "liệt"))

        for ev, raw_score in candidates:
            norm_rel = min(raw_score / max_rel, 1.0)

            # 1. Authority factor
            authority = ev.authority_score

            # 2. Clinical safety factor (give precedence to red flags and contraindications)
            safety = 0.5
            if ev.evidence_type in ("emergency_protocol", "contraindication"):
                safety = 1.0 if is_emergency_query else 0.8
            elif "red_flag" in ev.concept or "urgent" in str(ev.applicability):
                safety = 0.9

            # 3. Freshness factor
            freshness = 0.85

            # 4. Jurisdiction factor (e.g. BYT for Vietnamese patients)
            source = self.registry.get(ev.source_id)
            jurisdiction = 1.0 if (source and source.jurisdiction == user_jurisdiction) else 0.7

            composite_score = (
                (norm_rel * 0.40)
                + (authority * 0.25)
                + (safety * 0.15)
                + (freshness * 0.10)
                + (jurisdiction * 0.10)
            )

            reranked.append((ev, round(composite_score, 4)))

        # Deduplicate by concept preserving highest score
        seen_concepts: set[str] = set()
        deduped: list[tuple[NormalizedEvidence, float]] = []
        reranked.sort(key=lambda x: x[1], reverse=True)

        for ev, score in reranked:
            if ev.concept not in seen_concepts:
                seen_concepts.add(ev.concept)
                deduped.append((ev, score))

        return deduped[:top_n]
