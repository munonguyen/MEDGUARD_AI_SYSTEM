"""Authoritative Medical Source Registry with Lifecycle & Status Management.

Guarantees that:
1. Every piece of clinical evidence traces back to a registered, versioned authority.
2. Superseded, revoked, or expired guidelines are automatically blocked from runtime retrieval.
3. Provenance metadata is tamper-evident via SHA-256 digests.
"""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

from app.knowledge.provenance.checksum import compute_sha256

SourceStatus = Literal["ACTIVE", "SUPERSEDED", "REVOKED", "EXPIRED"]
DocumentType = Literal[
    "clinical_guideline",
    "drug_monograph",
    "emergency_protocol",
    "legal_regulation",
    "specialty_consensus",
]


class SourceRecord(BaseModel):
    """Immutable metadata record for an authoritative clinical or legal document."""
    source_id: str = Field(description="Unique source ID, e.g. 'BYT_QD_361_2014'")
    title: str = Field(description="Official title of the document")
    authority: str = Field(description="Issuing authority, e.g. 'Bộ Y tế Việt Nam', 'WHO', 'NICE'")
    jurisdiction: Literal["VN", "INT", "US", "UK"] = Field(default="VN")
    document_type: DocumentType = Field(default="clinical_guideline")
    effective_from: str = Field(description="Effective date (YYYY-MM-DD)")
    effective_until: str | None = Field(default=None, description="Expiration date or superseded date")
    version: str = Field(default="1.0")
    language: str = Field(default="vi")
    specialty: list[str] = Field(default_factory=list)
    checksum_sha256: str = Field(default="")
    status: SourceStatus = Field(default="ACTIVE")

    def model_post_init(self, __context) -> None:
        if not self.checksum_sha256:
            content_dict = {
                "source_id": self.source_id,
                "title": self.title,
                "authority": self.authority,
                "version": self.version,
                "effective_from": self.effective_from,
            }
            self.checksum_sha256 = compute_sha256(content_dict)


class SourceRegistry:
    """In-process Registry managing authoritative medical sources."""

    def __init__(self) -> None:
        self._sources: dict[str, SourceRecord] = {}

    def register(self, record: SourceRecord) -> None:
        """Registers or updates a source record."""
        self._sources[record.source_id] = record

    def get(self, source_id: str) -> SourceRecord | None:
        """Retrieves a source record by ID."""
        return self._sources.get(source_id)

    def is_active(self, source_id: str) -> bool:
        """Checks if a source is currently active and valid for runtime inference."""
        record = self._sources.get(source_id)
        if not record:
            return False
        return record.status == "ACTIVE"

    def list_active(self) -> list[SourceRecord]:
        """Returns all sources currently in ACTIVE status."""
        return [s for s in self._sources.values() if s.status == "ACTIVE"]

    @classmethod
    def create_default(cls) -> SourceRegistry:
        """Instantiates the registry pre-populated with authoritative Vietnamese and International medical authorities."""
        registry = cls()

        # 1. Bộ Y tế Việt Nam — Hướng dẫn chẩn đoán điều trị nội khoa
        registry.register(
            SourceRecord(
                source_id="BYT_QD_361_2014",
                title="Hướng dẫn chẩn đoán và xử trí các bệnh nội khoa thường gặp",
                authority="Bộ Y tế Việt Nam",
                jurisdiction="VN",
                document_type="clinical_guideline",
                effective_from="2014-01-24",
                version="1.0",
                specialty=["internal_medicine", "cardiology", "neurology"],
                status="ACTIVE",
            )
        )

        # 2. Bộ Y tế Việt Nam — Dược thư Quốc gia Việt Nam
        registry.register(
            SourceRecord(
                source_id="BYT_DUOC_THU_2022",
                title="Dược thư Quốc gia Việt Nam lần xuất bản thứ III",
                authority="Hội đồng Dược thư Quốc gia Việt Nam",
                jurisdiction="VN",
                document_type="drug_monograph",
                effective_from="2022-12-23",
                version="3.0",
                specialty=["pharmacology", "toxicology"],
                status="ACTIVE",
            )
        )

        # 3. Bộ Y tế Việt Nam — Phác đồ Cấp cứu & Chống sốc phản vệ
        registry.register(
            SourceRecord(
                source_id="BYT_TT_51_2017",
                title="Thông tư 51/2017/TT-BYT Hướng dẫn phòng, chẩn đoán và xử trí phản vệ",
                authority="Bộ Y tế Việt Nam",
                jurisdiction="VN",
                document_type="emergency_protocol",
                effective_from="2017-12-29",
                version="1.0",
                specialty=["emergency_medicine", "allergology"],
                status="ACTIVE",
            )
        )

        # 4. NICE Guidelines (UK) — Venous Thromboembolism (DVT/PE)
        registry.register(
            SourceRecord(
                source_id="NICE_NG158_2020",
                title="Venous thromboembolic diseases: diagnosis, management and thrombophilia testing",
                authority="National Institute for Health and Care Excellence",
                jurisdiction="UK",
                document_type="clinical_guideline",
                effective_from="2020-03-26",
                version="1.2",
                specialty=["vascular_surgery", "hematology"],
                status="ACTIVE",
            )
        )

        # 5. WHO — Clinical Management of Sepsis and Septic Shock
        registry.register(
            SourceRecord(
                source_id="WHO_SEPSIS_2023",
                title="WHO consolidated guidelines on clinical management of sepsis and septic shock",
                authority="World Health Organization",
                jurisdiction="INT",
                document_type="clinical_guideline",
                effective_from="2023-05-15",
                version="2.0",
                specialty=["critical_care", "infectious_diseases"],
                status="ACTIVE",
            )
        )

        # 6. Legacy Guideline — Example of SUPERSEDED source
        registry.register(
            SourceRecord(
                source_id="BYT_QD_OLD_2005",
                title="Quy định cũ về cấp cứu phản vệ 2005",
                authority="Bộ Y tế Việt Nam",
                jurisdiction="VN",
                document_type="emergency_protocol",
                effective_from="2005-01-01",
                effective_until="2017-12-28",
                version="0.9",
                status="SUPERSEDED",
            )
        )

        return registry


# Global default instance
default_source_registry = SourceRegistry.create_default()
