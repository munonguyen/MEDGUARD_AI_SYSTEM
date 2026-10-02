"""Monotonic clinical safety floor with V28.1 context reasoning.

All clinical detectors feed this one contract before OOD filtering and before
the normal triage resolver. Downstream layers may escalate the disposition;
they may never return a level below this floor.

V28.1 adds two protections without weakening the historical safety stack:
- context-aware domain assessments may raise the floor to URGENT/EMERGENCY;
- symptoms mentioned only as contingency guidance ("nếu ... thì làm gì?") are
  not fed to legacy keyword/semantic detectors as if they were current facts.

Post-V10 corrections may refine a detector's false-positive interpretation
before it enters the monotonic maximum. This preserves the safety-floor
contract while preventing a broad semantic concept from turning every minor
or hypothetical finding into a catastrophic emergency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Literal

from app.services.clinical_fact_parser import parse_semantic_clinical_facts
from app.services.clinical_reasoning.context_router import ClinicalContextRouter
from app.services.clinical_text import normalize_search_text
from app.services.clinical_threat_graph import ThreatLevel, evaluate_threat_graph
from app.services.end_organ_coupling import EndOrganCouplingAssessment, evaluate_end_organ_coupling
from app.services.evidence_strength_scorer import score_evidence_strength
from app.services.physiologic_consequence_engine import deduce_physiologic_consequences
from app.services.toxicology_signature_router import route_by_toxicity_signature


SafetyFloorDisposition = Literal["ROUTINE", "URGENT", "EMERGENCY"]
_RANK = {"ROUTINE": 1, "URGENT": 2, "EMERGENCY": 3}
_V28_CONTEXT_ROUTER = ClinicalContextRouter()
_CONDITIONAL_START = re.compile(r"\b(?:neu nhu|neu|gia su|truong hop|lo may)\b")


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


def _active_text_for_legacy_detectors(text: str, *, is_hypothetical: bool) -> str:
    """Remove a trailing contingency clause before legacy detector evaluation.

    Legacy detectors remain authoritative for current facts, but they were not
    originally designed to distinguish "tôi khó thở" from "nếu tôi khó thở thì
    làm gì?". V28 performs that scope distinction first. Returning an empty
    string for a pure contingency question is intentional: current-state safety
    is ROUTINE while the response layer can still explain what to do *if* the
    warning sign actually occurs.
    """
    if not is_hypothetical:
        return text
    norm = normalize_search_text(text)
    match = _CONDITIONAL_START.search(norm)
    if not match:
        return text
    return norm[: match.start()].strip(" ,.;:-")


def _anticoagulant_epistaxis_without_major_loss(text: str) -> bool:
    """Return true for anticoagulation-associated nosebleed without shock/major loss.

    Anticoagulant use raises the importance of epistaxis and warrants prompt
    medication-safety/clinical assessment. It does not, by itself, establish
    exsanguinating hemorrhage. Emergency evidence still wins when the text
    reports major-volume bleeding, another major bleeding site, overdose, or
    hemodynamic compromise.
    """
    norm = normalize_search_text(text)
    has_anticoagulant = any(
        marker in norm
        for marker in (
            "thuoc chong dong",
            "warfarin",
            "sintrom",
            "coumadin",
            "xarelto",
            "eliquis",
            "apixaban",
            "rivaroxaban",
            "dabigatran",
        )
    )
    has_epistaxis = any(
        marker in norm
        for marker in (
            "chay mau cam",
            "chay mau mui",
            "mau cam",
            "mau mui",
        )
    )
    if not (has_anticoagulant and has_epistaxis):
        return False

    major_loss_markers = (
        "chay mau o at",
        "mau chay o at",
        "chay mau rat nhieu",
        "mat mau nhieu",
        "non ra mau",
        "ho ra mau",
        "tieu ra mau",
        "di ngoai phan den",
        "phan den nhu ba ca phe",
        "xuat huyet tieu hoa",
        "xuat huyet noi",
        "qua lieu",
        "uong qua lieu",
        "tut huyet ap",
        "truy mach",
        "soc mat mau",
        "nga quy",
        "bat tinh",
        "ngat xiu",
        "gan ngat",
        "sap ngat",
        "choang vang",
        "choang va",
    )
    return not any(marker in norm for marker in major_loss_markers)


def evaluate_clinical_safety_floor(
    text: str,
    vitals: dict[str, Any] | None = None,
) -> ClinicalSafetyFloor:
    """Aggregate independent clinical modules through a conservative maximum."""
    # V28 parsing is fail-soft: if a context module fails, the established
    # deterministic detector stack still runs unchanged.
    v28_context = None
    try:
        v28_context = _V28_CONTEXT_ROUTER.parse(text)
    except Exception:
        v28_context = None

    detector_text = _active_text_for_legacy_detectors(
        text,
        is_hypothetical=bool(v28_context and v28_context.is_hypothetical),
    )

    fact_set = parse_semantic_clinical_facts(detector_text)
    evidence = score_evidence_strength(detector_text)
    tox = route_by_toxicity_signature(detector_text)
    threat = evaluate_threat_graph(fact_set, vitals or {})
    consequences = deduce_physiologic_consequences(fact_set)
    coupling = evaluate_end_organ_coupling(detector_text, vitals)
    bounded_anticoagulant_epistaxis = _anticoagulant_epistaxis_without_major_loss(detector_text)

    candidates: list[tuple[SafetyFloorDisposition, float, str, str]] = []

    # V28 is an additional deterministic safety source. It can only contribute
    # URGENT/EMERGENCY candidates; ROUTINE never downgrades another detector.
    if v28_context and v28_context.domain_assessment:
        v28_level = str(v28_context.domain_assessment.risk_level).upper()
        if v28_level in {"URGENT", "EMERGENCY"}:
            candidates.append(
                (
                    v28_level,  # type: ignore[arg-type]
                    0.95 if v28_level == "EMERGENCY" else 0.86,
                    "v28_clinical_context_router",
                    v28_context.domain_assessment.rationale,
                )
            )

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
        if bounded_anticoagulant_epistaxis:
            candidates.append((
                "URGENT",
                0.94,
                "clinical_threat_graph",
                (
                    "Chảy máu cam ở người đang dùng thuốc chống đông cần được đánh giá sớm, "
                    "nhưng chưa có dữ kiện về xuất huyết lượng lớn hoặc suy tuần hoàn để đặt "
                    "mức sàn cấp cứu chỉ từ việc dùng thuốc chống đông."
                ),
            ))
        else:
            candidates.append(("EMERGENCY", 0.99, "clinical_threat_graph", threat.primary_threat_summary))
    elif threat.max_threat_level in (ThreatLevel.HIGH, ThreatLevel.MODERATE):
        candidates.append(("URGENT", 0.88, "clinical_threat_graph", threat.primary_threat_summary))

    if consequences.has_emergency_consequence:
        candidates.append(("EMERGENCY", 0.98, "physiologic_consequence_engine", consequences.primary_threat_summary))
    if coupling.is_emergency:
        candidates.append(("EMERGENCY", coupling.confidence, "end_organ_coupling", coupling.rationale))

    if not candidates:
        # Preserve the fact that a pure hypothetical question was intentionally
        # scoped as non-current so downstream diagnostics can audit the choice.
        if v28_context and v28_context.is_hypothetical:
            return ClinicalSafetyFloor(
                disposition="ROUTINE",
                confidence=0.80,
                sources=("v28_clinical_context_router",),
                reasons=(
                    "Các dấu hiệu nguy hiểm được nêu dưới dạng giả định/dự phòng, không phải finding hiện tại.",
                ),
                end_organ_coupling=coupling,
            )
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
