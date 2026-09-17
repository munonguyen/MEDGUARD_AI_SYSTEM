"""Clinical Threat Graph for MedGuard AI (V6 Architecture).

Evaluates 12 physiologic and functional threat dimensions strictly based on
structured, evidence-grounded ClinicalFactSet models, completely decoupled from
raw natural language strings or text expressions.

Principles:
- Abstract Physiologic Threat: Detects organ-system failure patterns
  (e.g., circulatory compromise, metabolic crisis, acute surgical abdomen,
  limb ischemia, sudden vision loss) independently of named disease entities.
- Decoupled Contract: Evaluates ClinicalFactSet, NEVER raw user text.
- Multi-Dimensional Synergy: Multiple high/moderate threats compose into high acuity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.models.clinical_events import (
    ClinicalFactSet,
    OnsetTrajectory,
    SeverityLevel,
)


class ThreatLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def severity_score(self) -> int:
        scores = {
            ThreatLevel.NONE: 0,
            ThreatLevel.LOW: 1,
            ThreatLevel.MODERATE: 2,
            ThreatLevel.HIGH: 3,
            ThreatLevel.CRITICAL: 4,
        }
        return scores[self]


@dataclass(frozen=True)
class DimensionAssessment:
    dimension: str
    level: ThreatLevel
    confidence: float
    findings: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass(frozen=True)
class ThreatGraphResult:
    assessments: dict[str, DimensionAssessment]
    max_threat_level: ThreatLevel
    critical_dimensions: list[str]
    high_dimensions: list[str]
    composite_threat_score: int
    primary_threat_summary: str

    def has_threat_at_least(self, level: ThreatLevel) -> bool:
        return self.max_threat_level.severity_score >= level.severity_score


# ---------------------------------------------------------------------------
# Individual Dimension Evaluators (Decoupled from Raw Text)
# ---------------------------------------------------------------------------

def _eval_airway(fact_set: ClinicalFactSet, vitals: dict[str, float]) -> DimensionAssessment:
    """1. Airway Compromise & Stridor."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50

    if (
        fact_set.has_consequence(["airway_compromise", "neuromuscular_airway_compromise"])
        or fact_set.has_concept(["airway_obstruction_or_severe_dyspnea", "tetanic_spasm", "tension_pneumothorax"])
    ):
        findings.append("Nguy cơ tắc nghẽn hoặc co thắt đường thở cấp (stridor / co cứng cơ hô hấp / tràn khí áp lực)")
        level = ThreatLevel.CRITICAL
        conf = 0.98

    return DimensionAssessment("airway", level, conf, findings)


def _eval_breathing(fact_set: ClinicalFactSet, vitals: dict[str, float]) -> DimensionAssessment:
    """2. Acute Respiratory Failure & Severe Dyspnea."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50

    spo2 = vitals.get("spo2")
    if spo2 is not None and spo2 <= 90:
        findings.append(f"Suy hô hấp cấp đe dọa tính mạng (SpO2 tụt còn {int(spo2)}%)")
        level = ThreatLevel.CRITICAL
        conf = 0.99
    elif (
        fact_set.has_functional_loss("inability_to_speak_full_sentences")
        or fact_set.has_consequence("airway_compromise")
        or fact_set.has_concept(["tension_pneumothorax", "acute_pulmonary_edema", "fat_embolism_or_pulmonary_embolism"])
    ):
        findings.append("Khó thở kịch phát không nói trọn câu / phù phổi cấp / thuyên tắc mỡ / tràn khí áp lực")
        level = ThreatLevel.CRITICAL
        conf = 0.95
    elif spo2 is not None and spo2 <= 93:
        findings.append(f"Giảm oxy máu mức độ vừa (SpO2: {int(spo2)}%)")
        level = ThreatLevel.HIGH
        conf = 0.90

    return DimensionAssessment("breathing", level, conf, findings)


def _eval_circulation(fact_set: ClinicalFactSet, vitals: dict[str, float]) -> DimensionAssessment:
    """3. Circulatory Compromise & Hemodynamic Shock."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50

    sbp = vitals.get("sbp")
    hr = vitals.get("hr")

    if sbp is not None and sbp < 90:
        findings.append(f"Huyết áp tụt sâu đe dọa sốc tuần hoàn (HA tâm thu: {int(sbp)} mmHg)")
        level = ThreatLevel.CRITICAL
        conf = 0.99
    elif (
        fact_set.has_consequence(["circulatory_compromise", "catastrophic_vascular_threat", "internal_hemorrhage_and_shock", "exsanguinating_hemorrhage"])
        or fact_set.has_concept(["hemodynamic_shock", "aortic_dissection_or_rupture", "splenic_rupture", "acute_coronary_syndrome", "femoral_hematoma_or_rupture", "cardiac_tamponade", "anaphylaxis_shock", "boerhaave_syndrome"])
    ):
        findings.append("Sốc tuần hoàn / trụy mạch / hội chứng vành cấp / vỡ tạng chảy máu / bóc tách động mạch / chèn ép tim")
        level = ThreatLevel.CRITICAL
        conf = 0.98
    elif hr is not None and (hr > 130 or hr < 45):
        findings.append(f"Rối loạn nhịp tim nguy hiểm đe dọa huyết động ({int(hr)} l/p)")
        level = ThreatLevel.HIGH
        conf = 0.90

    return DimensionAssessment("circulation", level, conf, findings)


def _eval_neurology(fact_set: ClinicalFactSet, vitals: dict[str, float]) -> DimensionAssessment:
    """4. Acute Neurologic Deficit / Altered Mental Status."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50

    if (
        fact_set.has_functional_loss(["loss_of_motor_power", "loss_of_swallowing_and_jaw_opening", "loss_of_hearing"])
        or fact_set.has_consequence(["acute_neurologic_deficit", "neuromuscular_airway_compromise", "raised_intracranial_pressure_or_meningeal_irritation", "sensory_organ_ischemia"])
        or fact_set.has_concept(["acute_stroke", "intracranial_catastrophe", "tetanic_spasm", "spinal_cord_compression", "sudden_hearing_loss"])
    ):
        findings.append("Thiếu sót thần kinh khu trú cấp tính / đột quỵ não / co cứng uốn ván / tăng áp lực nội sọ / chèn ép tủy / điếc đột ngột")
        level = ThreatLevel.CRITICAL
        conf = 0.98

    return DimensionAssessment("neurology", level, conf, findings)


def _eval_sepsis_infection(fact_set: ClinicalFactSet, vitals: dict[str, float]) -> DimensionAssessment:
    """5. Severe Sepsis / Toxic Shock Syndrome."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50

    if (
        fact_set.has_concept(["tumor_lysis_or_septic_shock", "urosepsis_hypotension", "toxic_epidermal_necrolysis", "postpartum_sepsis"])
        or (fact_set.has_consequence("metabolic_crisis") and fact_set.has_consequence("organ_hypoperfusion_or_necrosis"))
    ):
        findings.append("Hội chứng nhiễm trùng nhiễm độc nặng / sốc nhiễm khuẩn / SJS-TEN / nhiễm trùng hậu sản / suy đa tạng")
        level = ThreatLevel.CRITICAL
        conf = 0.98

    return DimensionAssessment("sepsis_infection", level, conf, findings)


def _eval_major_bleeding(fact_set: ClinicalFactSet, vitals: dict[str, float]) -> DimensionAssessment:
    """6. Exsanguinating / Non-compressible Hemorrhage."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50

    if (
        fact_set.has_consequence(["exsanguinating_hemorrhage", "internal_hemorrhage_and_shock"])
        or fact_set.has_concept(["massive_hemorrhage", "splenic_rupture"])
    ):
        findings.append("Xuất huyết cấp tính đe dọa trụy mạch (nôn máu ồ ạt / ho máu sét đánh / vỡ tạng chảy máu trong / xuất huyết tiêu hóa ồ ạt)")
        level = ThreatLevel.CRITICAL
        conf = 0.98

    return DimensionAssessment("major_bleeding", level, conf, findings)


def _eval_toxic_exposure(fact_set: ClinicalFactSet, vitals: dict[str, float]) -> DimensionAssessment:
    """7. Acute Toxic Exposure & Massive Overdose."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50

    if (
        fact_set.has_consequence("acute_toxic_metabolic_threat")
        or fact_set.has_concept("toxic_ingestion")
    ):
        findings.append("Ngộ độc cấp chất độc cực mạnh / ngộ độc thuốc quá liều cấp tính")
        level = ThreatLevel.CRITICAL
        conf = 0.98

    return DimensionAssessment("toxic_exposure", level, conf, findings)


def _eval_pregnancy_danger(fact_set: ClinicalFactSet, vitals: dict[str, float]) -> DimensionAssessment:
    """8. Pregnancy-Related Life Threat."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50

    if (
        fact_set.has_consequence("obstetric_catastrophe")
        or fact_set.has_concept(["obstetric_catastrophe", "postpartum_sepsis"])
    ):
        findings.append("Cấp cứu sản khoa đe dọa tính mạng mẹ và thai (chửa ngoài tử cung vỡ / tiền sản giật nặng)")
        level = ThreatLevel.CRITICAL
        conf = 0.98

    return DimensionAssessment("pregnancy_danger", level, conf, findings)


def _eval_surgical_abdomen(fact_set: ClinicalFactSet, vitals: dict[str, float]) -> DimensionAssessment:
    """9. Acute Surgical Abdomen & Peritonism."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50

    if (
        fact_set.has_consequence(["peritoneal_irritation", "bowel_strangulation_or_obstruction", "organ_ischemia_necrosis_threat"])
        or fact_set.has_concept(["abdominal_rigidity", "strangulated_hernia", "intussusception", "mesenteric_ischemia"])
    ):
        findings.append("Bụng ngoại khoa cấp tính (thủng tạng rỗng / viêm phúc mạc toàn thể / thoát vị nghẹt / tắc ruột / lồng ruột / thiếu máu mạc treo)")
        level = ThreatLevel.CRITICAL
        conf = 0.98
    elif fact_set.has_concept("acute_appendicitis"):
        findings.append("Dấu hiệu viêm ruột thừa cấp cần đánh giá ngoại khoa sớm")
        level = ThreatLevel.HIGH
        conf = 0.88

    return DimensionAssessment("surgical_abdomen", level, conf, findings)


def _eval_vision_threat(fact_set: ClinicalFactSet, vitals: dict[str, float]) -> DimensionAssessment:
    """10. Vision-Threatening Acute Emergency."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50

    if (
        fact_set.has_functional_loss("loss_of_sight")
        or fact_set.has_consequence("retinal_or_optic_ischemia")
        or fact_set.has_concept(["vision_loss", "orbital_cellulitis_cavernous_sinus"])
    ):
        findings.append("Cấp cứu nhãn khoa tối khẩn (tắc động mạch võng mạc / amaurosis fugax / bong võng mạc / glaucoma cấp / vỡ nhãn cầu)")
        level = ThreatLevel.CRITICAL
        conf = 0.98

    return DimensionAssessment("vision_threat", level, conf, findings)


def _eval_limb_threat(fact_set: ClinicalFactSet, vitals: dict[str, float]) -> DimensionAssessment:
    """11. Limb-Threatening Ischemia & Compartment Syndrome."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50

    if (
        fact_set.has_consequence(["limb_perfusion_failure", "compartment_pressure_ischemia", "organ_ischemia_necrosis_threat", "catastrophic_vascular_threat"])
        or fact_set.has_concept(["arterial_occlusion", "compartment_syndrome", "vascular_access_rupture_threat", "ischemic_priapism", "femoral_hematoma_or_rupture"])
    ):
        findings.append("Thiếu máu chi cấp / chèn ép khoang / dọa vỡ mạch máu lớn đe dọa hoại tử và mất chi")
        level = ThreatLevel.CRITICAL
        conf = 0.98

    return DimensionAssessment("limb_threat", level, conf, findings)


def _eval_metabolic_crisis(fact_set: ClinicalFactSet, vitals: dict[str, float]) -> DimensionAssessment:
    """12. Acute Metabolic / Oncologic / Endocrine Crisis."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50

    if (
        fact_set.has_consequence(["metabolic_crisis", "organ_hypoperfusion_or_necrosis"])
        or fact_set.has_concept(["tumor_lysis_or_septic_shock", "thyroid_storm", "diabetic_ketoacidosis", "heat_stroke", "urosepsis_hypotension", "toxic_epidermal_necrolysis", "extensive_burn_injury"])
    ):
        findings.append("Cơn khủng hoảng chuyển hóa cấp / hội chứng ly giải u / bão giáp / nhiễm toan ceton ĐTĐ / sốc nhiệt ác tính")
        level = ThreatLevel.CRITICAL
        conf = 0.98

    return DimensionAssessment("metabolic_crisis", level, conf, findings)


# ---------------------------------------------------------------------------
# Composite Graph Evaluator (Strictly Decoupled)
# ---------------------------------------------------------------------------

def evaluate_threat_graph(
    fact_set: ClinicalFactSet,
    vitals_dict: dict[str, Any] | None = None,
) -> ThreatGraphResult:
    """Evaluate patient clinical findings across all 12 physiologic threat dimensions.
    
    Contract: Strictly accepts a structured ClinicalFactSet. Zero raw text operations.
    """
    if not isinstance(fact_set, ClinicalFactSet):
        raise TypeError(
            f"ThreatGraph Contract Violation: evaluate_threat_graph strictly requires ClinicalFactSet, "
            f"got {type(fact_set).__name__}. Raw text must be passed through Semantic Fact Parser first."
        )

    vitals: dict[str, float] = {}
    if vitals_dict:
        for k, v in vitals_dict.items():
            if isinstance(v, (int, float)):
                vitals[k.lower()] = float(v)

    evaluators = [
        _eval_airway(fact_set, vitals),
        _eval_breathing(fact_set, vitals),
        _eval_circulation(fact_set, vitals),
        _eval_neurology(fact_set, vitals),
        _eval_sepsis_infection(fact_set, vitals),
        _eval_major_bleeding(fact_set, vitals),
        _eval_toxic_exposure(fact_set, vitals),
        _eval_pregnancy_danger(fact_set, vitals),
        _eval_surgical_abdomen(fact_set, vitals),
        _eval_vision_threat(fact_set, vitals),
        _eval_limb_threat(fact_set, vitals),
        _eval_metabolic_crisis(fact_set, vitals),
    ]

    assessments: dict[str, DimensionAssessment] = {}
    critical_dims: list[str] = []
    high_dims: list[str] = []
    max_level = ThreatLevel.NONE
    composite_score = 0
    all_findings: list[str] = []

    for assess in evaluators:
        assessments[assess.dimension] = assess
        score = assess.level.severity_score
        composite_score += score
        if assess.level == ThreatLevel.CRITICAL:
            critical_dims.append(assess.dimension)
            all_findings.extend(assess.findings)
        elif assess.level == ThreatLevel.HIGH:
            high_dims.append(assess.dimension)
            all_findings.extend(assess.findings)

        if score > max_level.severity_score:
            max_level = assess.level

    summary = (
        "; ".join(all_findings[:3])
        if all_findings
        else "Không ghi nhận dấu hiệu đe dọa sinh lý nguy kịch cấp tính."
    )

    return ThreatGraphResult(
        assessments=assessments,
        max_threat_level=max_level,
        critical_dimensions=critical_dims,
        high_dimensions=high_dims,
        composite_threat_score=composite_score,
        primary_threat_summary=summary,
    )
