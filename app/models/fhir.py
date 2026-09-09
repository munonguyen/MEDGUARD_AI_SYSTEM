"""Pydantic model for FHIR export request."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class FhirExportRequest(BaseModel):
    patient_ref: str
    medications: list[dict[str, Any]] = Field(default_factory=list)
    observations: list[dict[str, Any]] = Field(default_factory=list)
    triage: dict[str, Any] | None = None
