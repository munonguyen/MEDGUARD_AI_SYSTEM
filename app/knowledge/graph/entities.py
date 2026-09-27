"""Clinical Entity Types and Schemas for Medical Knowledge Graph."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

EntityType = Literal[
    "Disease",
    "Drug",
    "DrugClass",
    "Symptom",
    "Finding",
    "RedFlag",
    "Treatment",
    "Contraindication",
    "Guideline",
    "Population",
    "LabTest",
    "Specialty",
]


class MedicalEntity(BaseModel):
    """A node in the Medical Knowledge Graph."""
    entity_id: str = Field(description="Unique canonical concept ID, e.g. 'drug.warfarin', 'disease.dvt'")
    name: str = Field(description="Standardized name in Vietnamese or international medical nomenclature")
    entity_type: EntityType = Field(description="Clinical ontological category")
    parent_class_id: str | None = Field(default=None, description="Parent class if this is a specific member, e.g. 'drug_class.anticoagulant'")
    aliases: list[str] = Field(default_factory=list, description="Synonyms, teencode, lay terms, and brand names")
    description: str = ""
