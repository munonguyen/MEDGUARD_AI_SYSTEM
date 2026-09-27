"""Clinical Relation Definitions with Provenance for Medical Knowledge Graph."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

RelationPredicate = Literal[
    "has_symptom",
    "has_red_flag",
    "differential_of",
    "treats",
    "contraindicated_in",
    "interacts_with",
    "recommends",
    "prohibits",
    "raises_concern_for",
]

RelationSeverity = Literal["minor", "moderate", "major", "critical"]


class MedicalRelation(BaseModel):
    """A directed edge in the Medical Knowledge Graph backed by authoritative evidence.

    Invariant: NO SOURCE, NO EDGE. Every relation must have an authoritative source_id.
    If the backing source is superseded, status transitions to INACTIVE (never silently deleted).
    """
    subject_id: str = Field(description="Source entity ID, e.g. 'drug.warfarin'")
    predicate: RelationPredicate = Field(description="Ontological relationship type")
    object_id: str = Field(description="Target entity ID, e.g. 'drug.ibuprofen'")
    severity: RelationSeverity = Field(default="major")
    mechanism: str = Field(description="Clinical or biochemical mechanism of the relationship")
    source_id: str = Field(description="Foreign key to SourceRegistry, e.g. 'BYT_DUOC_THU_2022'")
    version: str = Field(default="1.0")
    status: Literal["ACTIVE", "INACTIVE"] = Field(default="ACTIVE")

    def model_post_init(self, __context) -> None:
        if not self.source_id or not self.source_id.strip():
            raise ValueError(f"Invariant Violation: NO SOURCE, NO EDGE. Relation {self.subject_id} -> {self.predicate} -> {self.object_id} lacks source_id.")
