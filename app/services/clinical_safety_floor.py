"""Candidate V10 monotonic clinical safety floor.

All clinical detectors feed this one contract before OOD filtering and before
the normal triage resolver.  Downstream layers may escalate the disposition;
they may never return a level below this floor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.services.clinical_fact_parser import parse_semantic_clinical_facts
from app.services.clinical_threat_graph import ThreatLevel, evaluate_threat_graph
from app.services.end_organ_coupling import EndOrganCouplingAssessment, evaluate_end_organ_coupling
from app.services.evidence_strength_scorer import score_evidence_strength
from app.services.physiologic_consequence_engine import deduce_physiologic_consequences
from app.services.toxicology_signature_router import route_by_toxicity_signature


SafetyFloorDisposition = Literal["ROUTINE", "URGENT", "EMERGENCY"]
_RANK = {"ROUTINE": 1, "URGENT": 2, "EMERGENCY": 3}


@dataclass(frozen=True)
class ClinicalSafetyFloor:
    disposition: SafetyFloorDisposition
    confidence: float
    sources: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)
    ood_downgrade_revoked: bool = False
    toxicology_emergency: bool = False
    end_organ_coupling: EndOrganCouplingAssessment = field(default_factory=EndOrganCouplingAssessment)

    @property
    def is_emergency(self) -> bool:
        return self.disposition == "EMERGENCY"


def evaluate_clinical_safety_floor(
    text: str,
    vitals: dict[str, Any] | None = None,
) -> ClinicalSafetyFloor:
    """Aggregate independent clinical modules through a conservative maximum."""
    fact_set = parse_semantic_clinical_facts(text)
    evidence = score_evidence_strength(text)
    tox = route_by_toxicity_signature(text)
    threat = evaluate_threat_graph(fact_set, vitals or {})
    consequences = deduce_physiologic_consequences(fact_set)
    coupling = evaluate_end_organ_coupling(text, vitals)

    candidates: list[tuple[SafetyFloorDisposition, float, str, str]] = []

    if evidence.recommended_floor in _RANK:
        candidates.append((
            evidence.recommended_floor,  # type: ignore[arg-type]
            evidence.confidence,
            "evidence_strength_scorer",
            evidence.rationale,
        ))
    if tox.is_emergency_toxidrome:
        candidates.append(("EMERGENCY", tox.confidence, "toxicology_signature_router", tox.rationale))
    elif tox.is_toxicology_eligible:
        candidates.append(("URGENT", tox.confidence, "toxicology_signature_router", tox.rationale))
    if threat.max_threat_level == ThreatLevel.CRITICAL:
        candidates.append(("EMERGENCY", 0.99, "clinical_threat_graph", threat.primary_threat_summary))
    elif threat.max_threat_level in (ThreatLevel.HIGH, ThreatLevel.MODERATE):
        candidates.append(("URGENT", 0.88, "clinical_threat_graph", threat.primary_threat_summary))
    if consequences.has_emergency_consequence:
        candidates.append(("EMERGENCY", 0.98, "physiologic_consequence_engine", consequences.primary_threat_summary))
    if coupling.is_emergency:
        candidates.append(("EMERGENCY", coupling.confidence, "end_organ_coupling", coupling.rationale))

    if not candidates:
        return ClinicalSafetyFloor(
            disposition="ROUTINE",
            confidence=0.60,
            end_organ_coupling=coupling,
        )

    max_rank = max(_RANK[item[0]] for item in candidates)
    governing = [item for item in candidates if _RANK[item[0]] == max_rank]
    disposition = governing[0][0]
    confidence = max(item[1] for item in governing)
    sources = tuple(dict.fromkeys(item[2] for item in governing))
    reasons = tuple(dict.fromkeys(item[3] for item in governing if item[3]))

    return ClinicalSafetyFloor(
        disposition=disposition,
        confidence=confidence,
        sources=sources,
        reasons=reasons,
        ood_downgrade_revoked=(disposition == "EMERGENCY"),
        toxicology_emergency=tox.is_emergency_toxidrome,
        end_organ_coupling=coupling,
    )

