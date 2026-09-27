"""Typed Data Contracts for Multi-Domain Clinical Evidence Packet & Citation Provenance.

Phase 3 Architecture Invariant:
1. Typed Pydantic Objects First: XML is purely a serialization format for prompt injection.
2. Complete Citation Provenance: Every evidence chunk is traceable to authority, version,
   jurisdiction, section, and cryptographic checksum.
3. Token Budget Adaptive Allocation: Chunks are budgeted per domain according to complexity.
"""

from __future__ import annotations

import hashlib
import html
from typing import Any, Literal
from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    """Authoritative medical guideline or regulatory source citation."""
    source_id: str = Field(description="Unique source ID, e.g. 'BYT-3982', 'WHO-RHINITIS'")
    title: str = Field(description="Full guideline title")
    publisher: str = Field(description="Publishing authority, e.g. 'Bộ Y Tế Việt Nam', 'WHO', 'NICE'")
    authority_tier: Literal["government_health", "guideline_or_regulator", "peer_reviewed_journal"] = Field(
        default="government_health"
    )
    url: str | None = Field(default=None, description="Official publication URL")
    version: str = Field(default="2025-2026", description="Edition / year of guideline")
    section: str = Field(default="Chung", description="Section or chapter referenced")
    jurisdiction: str = Field(default="VN", description="Geographic applicability, e.g. 'VN', 'GLOBAL'")
    checksum: str = Field(default="", description="Content verification hash")

    def model_post_init(self, __context: Any) -> None:
        if not self.checksum:
            raw = f"{self.source_id}:{self.title}:{self.publisher}:{self.version}"
            object.__setattr__(self, "checksum", hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12])


class ClinicalFact(BaseModel):
    """Atomic confirmed or negated clinical observation."""
    fact_id: str = Field(description="Fact identifier, e.g. 'F1', 'F2'")
    concept: str = Field(description="Standardized medical concept, e.g. 'calf_tightness', 'fever'")
    raw_span: str = Field(description="Raw text snippet from patient input")
    negated: bool = Field(default=False, description="True if symptom is explicitly ruled out by patient")
    anatomical_site: str | None = Field(default=None, description="Body location if applicable")
    temporal_offset: str | None = Field(default=None, description="Time marker, e.g. '-2d', 'today_morning'")
    certainty: Literal["confirmed", "suspected", "denied"] = Field(default="confirmed")


class SafetyConstraint(BaseModel):
    """Hard safety invariant that downstream models and reasoning agents MUST uphold."""
    constraint_id: str = Field(description="Identifier, e.g. 'SC_NO_OVERDIAGNOSIS'")
    type: Literal["FORBIDDEN_ACTION", "MANDATORY_ACTION", "DIFFERENTIAL_BOUNDARY"]
    description: str = Field(description="Clinical rule or prohibition")
    mandatory: bool = Field(default=True)


class Evidence(BaseModel):
    """Ranked evidence chunk with metadata and domain attribution."""
    evidence_id: str = Field(description="Compact ID, e.g. 'E1', 'E2'")
    domain: Literal["clinical", "drug", "guideline", "legal", "monitoring", "red_flags"] = Field(
        description="Knowledge domain"
    )
    title: str = Field(description="Chunk headline or rule title")
    section: str = Field(default="General", description="Section or category")
    content: str = Field(description="Verified clinical excerpt")
    source_ref: SourceRef = Field(description="Provenance source reference")
    rrf_score: float = Field(default=0.0, description="Reciprocal Rank Fusion score")


class ClinicalEvidencePacket(BaseModel):
    """Typed Master Clinical Evidence Packet for Agent A & Critic Agent B."""
    packet_id: str = Field(description="Packet identifier")
    kb_version: str = Field(default="2026.09-v11", description="Knowledge base release version")
    raw_user_query: str = Field(description="Untouched user query")
    patient_facts: list[ClinicalFact] = Field(default_factory=list, description="Positive observations")
    negative_findings: list[ClinicalFact] = Field(default_factory=list, description="Ruled out observations")
    patient_concerns: list[str] = Field(default_factory=list, description="Patient anxiety/hypotheses (NOT diagnosis)")
    clinical_evidence: list[Evidence] = Field(default_factory=list)
    drug_evidence: list[Evidence] = Field(default_factory=list)
    guideline_evidence: list[Evidence] = Field(default_factory=list)
    legal_evidence: list[Evidence] = Field(default_factory=list)
    hard_safety_constraints: list[SafetyConstraint] = Field(default_factory=list)
    source_registry: list[SourceRef] = Field(default_factory=list)

    @property
    def all_evidence(self) -> list[Evidence]:
        """Flattened list of all evidence items across domains."""
        return (
            self.clinical_evidence
            + self.drug_evidence
            + self.guideline_evidence
            + self.legal_evidence
        )

    def to_xml_prompt(self) -> str:
        """Serialize typed packet to clean Anthropic-style XML prompt."""
        facts_xml = "\n".join(
            f"    <fact id='{f.fact_id}' concept='{html.escape(f.concept)}' site='{html.escape(f.anatomical_site or 'N/A')}' time='{html.escape(f.temporal_offset or 'N/A')}'>{html.escape(f.raw_span)}</fact>"
            for f in self.patient_facts
        ) or "    <fact id='none'>Không có dữ kiện đặc biệt</fact>"

        negatives_xml = "\n".join(
            f"    <negative id='{f.fact_id}' concept='{html.escape(f.concept)}'>{html.escape(f.raw_span)}</negative>"
            for f in self.negative_findings
        ) or "    <negative id='none'>Không báo cáo triệu chứng âm tính</negative>"

        concerns_xml = "\n".join(
            f"    <concern stated_fear='{html.escape(c)}' is_diagnosis='false'/>"
            for c in self.patient_concerns
        ) or "    <concern stated_fear='none' is_diagnosis='false'/>"

        evidence_items = "\n".join(
            f"  <evidence id='{e.evidence_id}' domain='{e.domain}' source_id='{e.source_ref.source_id}'>\n"
            f"    <title>{html.escape(e.title)}</title>\n"
            f"    <source>{html.escape(e.source_ref.publisher)} - {html.escape(e.source_ref.title)} ({e.source_ref.version})</source>\n"
            f"    <content>{html.escape(e.content[:500])}</content>\n"
            f"  </evidence>"
            for e in self.all_evidence
        ) or "  <evidence id='E0' domain='general'>Dữ liệu lâm sàng tiêu chuẩn</evidence>"

        constraints_xml = "\n".join(
            f"    <constraint id='{sc.constraint_id}' type='{sc.type}'>{html.escape(sc.description)}</constraint>"
            for sc in self.hard_safety_constraints
        )

        return f"""<clinical_evidence_packet id='{self.packet_id}' kb_version='{self.kb_version}'>
  <canonical_patient_state>
    <positive_facts>
{facts_xml}
    </positive_facts>
    <negative_findings>
{negatives_xml}
    </negative_findings>
    <patient_concerns_anxieties>
{concerns_xml}
    </patient_concerns_anxieties>
  </canonical_patient_state>

  <verified_evidence_items>
{evidence_items}
  </verified_evidence_items>

  <safety_constraints>
{constraints_xml}
  </safety_constraints>

  <raw_query>
    {html.escape(self.raw_user_query)}
  </raw_query>
</clinical_evidence_packet>"""
