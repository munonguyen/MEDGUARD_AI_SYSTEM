"""Canonical Clinical State for MedGuard AI System.

Unifies all upstream representations (demographics, parsed symptoms, extracted vitals,
medications, allergies, timeline, negations, uncertainties, risk factors, and clinical events)
into a single immutable state for all downstream reasoning gates and response generators.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.models.clinical_events import ClinicalAssertion, ClinicalEvent, ClinicalFactSet
from app.services.clinical_fact_parser import parse_semantic_clinical_facts
from app.services.clinical_text import normalize_search_text


class CanonicalClinicalState(BaseModel):
    """Unified single-source-of-truth clinical state representation."""
    model_config = ConfigDict(frozen=True)

    demographics: dict[str, Any] = Field(default_factory=dict)
    symptoms: list[dict[str, Any]] = Field(default_factory=list)
    vitals: list[dict[str, Any]] = Field(default_factory=list)
    medications: list[dict[str, Any]] = Field(default_factory=list)
    allergies: list[dict[str, Any]] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    negations: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    clinical_events: list[dict[str, Any]] = Field(default_factory=list)
    safety_floor: str = "ROUTINE"
    raw_text: str = ""
    normalized_text: str = ""

    @property
    def has_emergency_floor(self) -> bool:
        return self.safety_floor == "EMERGENCY"

    @property
    def has_vital_crisis(self) -> bool:
        for v in self.vitals:
            v_type = v.get("type", "")
            val = v.get("value", 0)
            if v_type == "bp_systolic" and val >= 180:
                return True
            if v_type == "spo2" and val < 90:
                return True
            if v_type == "heart_rate" and (val > 140 or val < 45):
                return True
        return False

    @property
    def active_symptom_names(self) -> list[str]:
        names = []
        for s in self.symptoms:
            if s.get("assertion", "present") == "present":
                names.append(s.get("name") or s.get("concept", ""))
        return [n for n in names if n]


def build_canonical_clinical_state(
    text: str,
    *,
    vitals: list[dict[str, Any]] | None = None,
    demographics: dict[str, Any] | None = None,
    medications: list[dict[str, Any]] | None = None,
    allergies: list[dict[str, Any]] | None = None,
    safety_floor: str = "ROUTINE",
) -> CanonicalClinicalState:
    """Build a unified CanonicalClinicalState from input text and patient context."""
    norm_text = normalize_search_text(text)
    fact_set: ClinicalFactSet = parse_semantic_clinical_facts(text)

    symptoms_list: list[dict[str, Any]] = []
    clinical_events_list: list[dict[str, Any]] = []
    negations_list: list[str] = [e.concept for e in fact_set.negated_events]
    uncertainties_list: list[str] = [e.concept for e in fact_set.events if e.assertion == ClinicalAssertion.UNCERTAIN]
    risk_factors_list: list[str] = []

    for event in fact_set.events:
        event_dict = event.model_dump()
        clinical_events_list.append(event_dict)
        if event.assertion == ClinicalAssertion.PRESENT:
            symptoms_list.append({
                "concept": event.concept,
                "name": event.concept,
                "organ_system": event.organ_system,
                "severity": event.severity.value,
                "onset": event.onset.value,
                "body_site": event.body_site,
                "evidence_span": event.evidence_span,
                "certainty": event.certainty,
                "assertion": "present",
            })
    from app.services.clinical_text import extract_clinical_facts
    raw_facts = extract_clinical_facts(text)
    for s in raw_facts.confirmed_symptoms:
        if not any(sym.get("name") == s for sym in symptoms_list):
            symptoms_list.append({"name": s, "concept": s, "assertion": "present"})
    for n in raw_facts.negative_findings:
        if n not in negations_list:
            negations_list.append(n)

    # Detect common risk factors from normalized text
    if any(k in norm_text for k in ("tang huyet ap", "cao huyet ap", "hypertension")):
        risk_factors_list.append("hypertension")
    if any(k in norm_text for k in ("tieu duong", "dai thao duong", "diabetes")):
        risk_factors_list.append("diabetes")
    if any(k in norm_text for k in ("hut thuoc", "thuoc la", "smoker")):
        risk_factors_list.append("smoking")
    if any(k in norm_text for k in ("tim mach", "benh tim", "cardiac_disease")):
        risk_factors_list.append("heart_disease")

    # Format vitals safely
    safe_vitals: list[dict[str, Any]] = []
    for v in vitals or []:
        if isinstance(v, dict):
            safe_vitals.append(dict(v))

    return CanonicalClinicalState(
        demographics=dict(demographics or {}),
        symptoms=symptoms_list,
        vitals=safe_vitals,
        medications=list(medications or []),
        allergies=list(allergies or []),
        timeline=[],
        negations=negations_list,
        uncertainties=uncertainties_list,
        risk_factors=risk_factors_list,
        clinical_events=clinical_events_list,
        safety_floor=safety_floor,
        raw_text=text,
        normalized_text=norm_text,
    )
