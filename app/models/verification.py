"""Typed Data Contracts for Evidence & Citation Guard / Verifier.

Phase 3 Core Architecture:
Separates Citation Verification from Clinical Safety:
- Verifies that every cited evidence chunk exists in registry.
- Verifies that cited text logically substantiates the claim.
- Detects fabricated citations, stale sources, or jurisdiction mismatches.
"""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


EvidenceRelation = Literal["SUPPORTS", "PARTIALLY_SUPPORTS", "CONTRADICTS", "NOT_RELEVANT"]


class CitationAudit(BaseModel):
    """Audit result for a single claim-evidence linkage."""
    claim_id: str
    evidence_id: str
    source_id: str
    citation_valid: bool
    evidence_substantiates_claim: bool
    relation: EvidenceRelation = "SUPPORTS"
    audit_notes: str = ""


class EvidenceVerificationResult(BaseModel):
    """Comprehensive output of the Evidence & Citation Verifier."""
    verified: bool = Field(description="True if all claims have valid, substantiated citations")
    unsupported_claim_ids: list[str] = Field(default_factory=list, description="Claims lacking valid evidence")
    invalid_citations: list[str] = Field(default_factory=list, description="Evidence IDs cited but not in packet")
    stale_sources: list[str] = Field(default_factory=list, description="Sources flagged as superseded or expired")
    audits: list[CitationAudit] = Field(default_factory=list)
    verification_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)
