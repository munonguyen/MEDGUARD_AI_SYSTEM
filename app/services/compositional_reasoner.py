"""Compositional Syndrome Reasoner for MedGuard AI (V5).

Decouples clinical diagnosis identification from emergency risk evaluation:
- Diagnosis Confidence: reflects certainty of the exact clinical disease entity.
- Triage Risk Confidence: reflects certainty of whether an acute, organ-threatening,
  or life-threatening physiologic process requires emergency escalation.

Core Principles:
1. "Uncertainty-Aware Composition":
   Unknown diagnosis (diagnosis_conf: 0.35) + Critical Threat Pattern -> EMERGENCY (risk_conf: 0.98).
2. "Benign Physiologic Pattern Gate":
   High-acuity keyword + Benign physiologic context (costochondritis, simple pollen rhinitis,
   superficial scratch) -> ROUTINE with high specificity (>= 95%).
3. Synergy: Multiple MODERATE/HIGH threats compose into EMERGENCY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.services.clinical_text import (
    contains_affirmed_phrase,
    normalize_search_text,
)
from app.services.clinical_threat_graph import (
    ThreatGraphResult,
    ThreatLevel,
    evaluate_threat_graph,
)

TriageDisposition = Literal["EMERGENCY", "URGENT", "ROUTINE"]


@dataclass(frozen=True)
class RiskHypothesis:
    disposition: TriageDisposition
    risk_confidence: float
    diagnosis_confidence: float
    primary_syndrome_label: str
    threat_summary: str
    red_flags: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    uncertainty_flag: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition,
            "risk_confidence": round(self.risk_confidence, 4),
            "diagnosis_confidence": round(self.diagnosis_confidence, 4),
            "primary_syndrome_label": self.primary_syndrome_label,
            "threat_summary": self.threat_summary,
            "red_flags": self.red_flags,
            "reasons": self.reasons,
            "uncertainty_flag": self.uncertainty_flag,
        }


# High-specificity benign patterns to preserve specificity and avoid over-triage
_BENIGN_PATTERNS: list[dict[str, Any]] = [
    {
        "id": "benign_costochondritis",
        "label": "Đau thành ngực / viêm sụn sườn thành ngực lành tính",
        "all_required": ["tho sau", "an tay", "ngoi yen"],
        "any_required": ["dau nhoi", "dau o nguc"],
        "forbidden": ["kho tho du doi", "tut huyet ap", "ngat", "va mo hoi", "lan len cam", "lan xuong tay"],
    },
    {
        "id": "benign_allergic_rhinitis",
        "label": "Viêm mũi dị ứng lành tính / hắt hơi sổ mũi",
        "all_required": ["hat hoi", "chay nuoc mui"],
        "forbidden": ["tho rit", "kho tho", "phu moi", "tut huyet ap"],
    },
    {
        "id": "benign_dry_eyes",
        "label": "Mỏi điều tiết mắt / khô mắt văn phòng lành tính",
        "all_required": ["kho mat", "may tinh"],
        "forbidden": ["toi sam", "mat thi luc", "cau vong", "dau nhuc du doi", "hoa chat"],
    },
    {
        "id": "benign_superficial_scratch",
        "label": "Trầy xước da nông lành tính",
        "all_required": ["tray xuoc"],
        "forbidden": ["chay mau khong cam", "rach sau", "lo xuong", "phun thanh tia"],
    },
    {
        "id": "benign_routine_checkup",
        "label": "Tư vấn sức khỏe định kỳ",
        "all_required": ["dinh ky", "binh thuong"],
        "forbidden": ["dau du doi", "tut huyet ap", "sot cao"],
    },
]


def _check_benign_pattern(norm: str) -> tuple[bool, str | None]:
    """Check if patient presents an unambiguously benign condition without threat features."""
    for bp in _BENIGN_PATTERNS:
        # Check all required markers
        if not all(contains_affirmed_phrase(norm, marker) for marker in bp["all_required"]):
            continue
        # Check any required markers
        if "any_required" in bp:
            if not any(contains_affirmed_phrase(norm, marker) for marker in bp["any_required"]):
                continue
        # Check forbidden red flags
        if any(contains_affirmed_phrase(norm, marker) for marker in bp.get("forbidden", [])):
            continue
        return True, bp["label"]
    return False, None


def evaluate_compositional_risk(
    text: str,
    vitals_dict: dict[str, Any] | None = None,
    extracted_facts: dict[str, Any] | None = None,
) -> RiskHypothesis:
    """Evaluate compositional risk, decoupling diagnosis confidence from risk confidence."""
    norm = normalize_search_text(text)

    # 1. Run Clinical Threat Graph across 12 physiologic dimensions
    threat_result = evaluate_threat_graph(text, vitals_dict)

    # 2. Check for Benign Pattern Gate (High Specificity Preservation)
    if threat_result.max_threat_level == ThreatLevel.NONE:
        is_benign, benign_label = _check_benign_pattern(norm)
        if is_benign:
            return RiskHypothesis(
                disposition="ROUTINE",
                risk_confidence=0.98,
                diagnosis_confidence=0.85,
                primary_syndrome_label=benign_label or "Tình trạng lành tính ổn định",
                threat_summary="Không có dấu hiệu đe dọa sinh lý; hình thái triệu chứng lành tính.",
                red_flags=[],
                reasons=[f"Phù hợp {benign_label}; không ghi nhận dấu hiệu nguy kịch."],
                uncertainty_flag=False,
            )

    # 3. Critical Threat Escalation
    # If any dimension is CRITICAL -> Immediate EMERGENCY
    if threat_result.max_threat_level == ThreatLevel.CRITICAL:
        findings = []
        for dim in threat_result.critical_dimensions:
            findings.extend(threat_result.assessments[dim].findings)

        return RiskHypothesis(
            disposition="EMERGENCY",
            risk_confidence=0.99,
            diagnosis_confidence=0.60,  # Low diagnosis cert is OK; emergency cert is high!
            primary_syndrome_label=f"Hội chứng đe dọa sinh lý cấp ({', '.join(threat_result.critical_dimensions)})",
            threat_summary=threat_result.primary_threat_summary,
            red_flags=findings,
            reasons=[
                f"Phát hiện dấu hiệu đe dọa cấp cứu tại chiều: {', '.join(threat_result.critical_dimensions)}.",
                threat_result.primary_threat_summary,
            ],
            uncertainty_flag=False,
        )

    # 4. Multi-Dimensional High Threat Composition
    # If >= 2 dimensions are HIGH -> Synergistic EMERGENCY
    if len(threat_result.high_dimensions) >= 2:
        findings = []
        for dim in threat_result.high_dimensions:
            findings.extend(threat_result.assessments[dim].findings)

        return RiskHypothesis(
            disposition="EMERGENCY",
            risk_confidence=0.96,
            diagnosis_confidence=0.50,
            primary_syndrome_label=f"Tổ hợp hội chứng đa cơ quan tiến triển ({', '.join(threat_result.high_dimensions)})",
            threat_summary=threat_result.primary_threat_summary,
            red_flags=findings,
            reasons=[
                f"Tổ hợp đa chiều đe dọa nguy cơ cao: {', '.join(threat_result.high_dimensions)}.",
                threat_result.primary_threat_summary,
            ],
            uncertainty_flag=False,
        )

    # 5. Single High Dimension -> URGENT with strong consideration
    if len(threat_result.high_dimensions) == 1:
        dim = threat_result.high_dimensions[0]
        assess = threat_result.assessments[dim]
        return RiskHypothesis(
            disposition="URGENT",
            risk_confidence=0.88,
            diagnosis_confidence=0.65,
            primary_syndrome_label=f"Nguy cơ tiến triển cấp tính chiều {dim}",
            threat_summary=assess.findings[0] if assess.findings else "Cần theo dõi y tế sớm",
            red_flags=assess.findings,
            reasons=[f"Ghi nhận triệu chứng cảnh báo chiều {dim}: {assess.findings}"],
            uncertainty_flag=False,
        )

    # 6. Default / Low Threat
    if threat_result.max_threat_level == ThreatLevel.MODERATE:
        return RiskHypothesis(
            disposition="URGENT",
            risk_confidence=0.75,
            diagnosis_confidence=0.50,
            primary_syndrome_label="Triệu chứng cần thăm khám chuyên khoa",
            threat_summary="Không có dấu hiệu đe dọa sinh lý nguy kịch nhưng cần theo dõi.",
            red_flags=[],
            reasons=["Triệu chứng mức độ trung bình cần kiểm tra y tế."],
            uncertainty_flag=True,
        )

    # 7. ROUTINE Baseline
    return RiskHypothesis(
        disposition="ROUTINE",
        risk_confidence=0.92,
        diagnosis_confidence=0.70,
        primary_syndrome_label="Triệu chứng nhẹ thông thường",
        threat_summary="Không ghi nhận dấu hiệu nguy kịch hay đe dọa sinh lý cấp tính.",
        red_flags=[],
        reasons=["Hình thái lâm sàng ổn định, không có dấu hiệu đỏ."],
        uncertainty_flag=False,
    )
