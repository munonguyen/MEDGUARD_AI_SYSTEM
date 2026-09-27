"""Context-preserving Clinical Chunker.

Breaks long guidelines and monographs into coherent chunks while preserving
hierarchical headers, concept tags, and section provenance.
"""

from __future__ import annotations

import re
from typing import Any
from pydantic import BaseModel, Field

from app.knowledge.provenance.checksum import compute_sha256


class ClinicalChunk(BaseModel):
    """A semantic chunk of clinical text retaining context headers and provenance."""
    chunk_id: str
    source_id: str
    section: str
    header: str
    text: str
    concept_tags: list[str] = Field(default_factory=list)
    checksum_sha256: str = ""

    def model_post_init(self, __context) -> None:
        if not self.checksum_sha256:
            self.checksum_sha256 = compute_sha256(self.text)


def chunk_clinical_text(
    content: str,
    source_id: str,
    default_concept: str = "clinical_guideline",
    max_chunk_words: int = 200,
) -> list[ClinicalChunk]:
    """Splits clinical text on section markers (###, Roman numerals, or double newlines)

    preserving section titles and concept tags.
    """
    paragraphs = re.split(r"\n{2,}", content.strip())
    chunks: list[ClinicalChunk] = []
    current_header = "Tổng quan"
    current_section = "1.0"

    for idx, p in enumerate(paragraphs, 1):
        clean_p = p.strip()
        if not clean_p:
            continue

        # Detect headers like "## 1. Triệu chứng" or "Điều 4."
        header_match = re.match(r"^(#{1,4}|Điều\s+\d+|Phần\s+[IVX]+|\d+\.)\s+(.+)$", clean_p, re.MULTILINE)
        if header_match:
            raw_title = header_match.group(2).strip()
            # Clean leading numbers if nested e.g. "1. Triệu chứng" -> "Triệu chứng"
            clean_title = re.sub(r"^(\d+\.|\d+\))\s*", "", raw_title).strip()
            current_header = clean_title or raw_title
            current_section = str(idx)

        chunk_id = f"CHK_{source_id}_{idx:04d}"
        tags = [default_concept]
        if "cấp cứu" in clean_p.lower() or "115" in clean_p:
            tags.append("emergency")
        if "chống chỉ định" in clean_p.lower():
            tags.append("contraindication")
        if "tương tác" in clean_p.lower():
            tags.append("drug_interaction")

        chunks.append(
            ClinicalChunk(
                chunk_id=chunk_id,
                source_id=source_id,
                section=current_section,
                header=current_header,
                text=clean_p,
                concept_tags=tags,
            )
        )

    return chunks
