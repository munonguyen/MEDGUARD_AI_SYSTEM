"""Normalized Knowledge Object Schema and Normalization Engine.

Converts heterogeneous raw documents into canonical, typed NormalizedEvidence
objects equipped with authority scores, population applicability, and cryptographic digests.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

from app.knowledge.provenance.checksum import compute_sha256
from app.knowledge.provenance.source_registry import SourceRegistry, default_source_registry


class NormalizedEvidence(BaseModel):
    """Canonical, typed representation of a verified medical guideline statement."""
    evidence_id: str = Field(description="Unique deterministic evidence ID, e.g. 'EV_DVT_0001'")
    concept: str = Field(description="Normalized concept tag, e.g. 'dvt_unilateral_swelling'")
    statement: str = Field(description="Authoritative clinical statement or recommendation")
    source_id: str = Field(description="Foreign key to SourceRegistry, e.g. 'BYT_QD_361_2014'")
    section: str = Field(default="1.0", description="Section or article number")
    evidence_type: Literal[
        "clinical_guideline",
        "drug_monograph",
        "emergency_protocol",
        "legal_regulation",
    ] = Field(default="clinical_guideline")
    authority_score: float = Field(default=0.95, ge=0.0, le=1.0)
    applicability: dict[str, Any] = Field(
        default_factory=lambda: {"population": "adult", "setting": "outpatient"},
        description="Clinical constraints (e.g. pediatric, pregnancy, renal)",
    )
    checksum_sha256: str = Field(default="")

    def model_post_init(self, __context) -> None:
        if not self.checksum_sha256:
            content_dict = {
                "evidence_id": self.evidence_id,
                "statement": self.statement,
                "source_id": self.source_id,
                "section": self.section,
            }
            self.checksum_sha256 = compute_sha256(content_dict)


def normalize_raw_item(
    raw_item: dict[str, Any],
    source_id: str,
    registry: SourceRegistry = default_source_registry,
) -> NormalizedEvidence:
    """Normalizes a raw clinical statement dict into a verified NormalizedEvidence instance."""
    source = registry.get(source_id)
    if not source:
        raise ValueError(f"Unknown source_id: '{source_id}' is not registered in SourceRegistry")
    if not registry.is_active(source_id):
        raise ValueError(f"Source '{source_id}' is inactive ({source.status}) and cannot be ingested")

    authority_score = 0.98 if source.authority == "Bộ Y tế Việt Nam" else 0.95
    if source.jurisdiction == "VN":
        authority_score = min(authority_score + 0.02, 1.0)

    evidence_id = raw_item.get("evidence_id") or f"EV_{compute_sha256(raw_item.get('statement', ''))[:8].upper()}"

    return NormalizedEvidence(
        evidence_id=evidence_id,
        concept=raw_item.get("concept", "general_clinical"),
        statement=raw_item.get("statement", "").strip(),
        source_id=source_id,
        section=raw_item.get("section", "1.0"),
        evidence_type=raw_item.get("evidence_type", source.document_type),  # type: ignore
        authority_score=authority_score,
        applicability=raw_item.get("applicability", {"population": "adult"}),
    )
