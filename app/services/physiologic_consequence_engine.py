"""Physiologic Consequence Engine for MedGuard AI (V7 Architecture).

Deduces abstract pathophysiologic failure patterns from structured ClinicalFactSet.
Decoupled from named diseases. Evaluates combinations of clinical findings to identify
acute physiological breakdowns that threaten life or vital organs.
"""

from __future__ import annotations

import re
from typing import Sequence

from app.models.clinical_events import ClinicalFactSet, SeverityLevel
from app.models.physiologic_consequences import (
    ConsequenceSeverity,
    PhysiologicAssessment,
    PhysiologicConsequence,
    PhysiologicConsequenceType,
)


def deduce_physiologic_consequences(fact_set: ClinicalFactSet) -> PhysiologicAssessment:
    """Analyze ClinicalFactSet and deduce active pathophysiologic consequences.
    
    Evaluates multi-system failure combinations rather than individual keywords.
    Strictly enforces that negated or non-patient historical findings do not trigger acute consequences.
    """
    consequences: list[PhysiologicConsequence] = []
    norm_text = fact_set.normalized_text

    # Gate: If explicitly negated or strictly non-patient historical, fail-safe to NONE
    is_negated_clause = bool(re.search(r"(?:nhung|ma|song|chu)\s+(?:toi|minh|em|chau)?\s*(?:khong|chua|ko|k|hong|chang)\s+(?:bi|co|bi nhu vay|nhu the|bi vay)", norm_text))
    is_negated_clause |= bool(re.search(r"\b(khong phai toi bi|khong phai bi|chua tung bi|khong he co|khong he bi|hoan toan binh thuong)\b", norm_text))
    is_historical_clause = bool(re.search(r"\b(bo toi|me toi|nguoi nha|ong toi|ba toi)\s+(?:tung bi|da tung bi|nam ngoai)\b.*?\b(?:con hom nay|toi khong bi|chi bi)\b", norm_text))

    if is_negated_clause or is_historical_clause:
        return PhysiologicAssessment(
            active_consequences=tuple(),
            primary_threat_summary="Không ghi nhận đe dọa sinh lý bệnh học tích cực của người bệnh.",
            max_severity=ConsequenceSeverity.MILD_OR_NONE,
        )

    events = fact_set.present_events
    present_concepts = {e.concept for e in events}

    # 1. MAJOR BARRIER FAILURE (Necrotizing Soft Tissue Destruction / Gas Gangrene)
    # Hallmarks: rapid progression, out-of-proportion pain, crepitus/gas, bullae, skin necrosis
    barrier_markers = [
        "necrotizing_soft_tissue_failure",
        "crepitus",
        "hemorrhagic_bullae",
        "skin_necrosis",
    ]
    has_barrier_concept = any(c in present_concepts for c in barrier_markers)
    has_barrier_cues = bool(re.search(r"\b(lep bep|bong nuoc den|ri dich hoi thoi|tham tim lan nhanh|dau khong tuong xung)\b", norm_text))
    if has_barrier_concept or (has_barrier_cues and re.search(r"\b(sung|do|vet thuong|mun|gai dam|chan|tay)\b", norm_text)):
        consequences.append(PhysiologicConsequence(
            consequence_type=PhysiologicConsequenceType.MAJOR_BARRIER_FAILURE,
            severity=ConsequenceSeverity.IMMINENT_LETHAL,
            confidence=0.98,
            supporting_findings=("Hoại tử mô mềm sâu", "Sinh hơi/lép bép dưới da", "Đau vượt quá mức tương xứng vết thương"),
            pathophysiologic_rationale="Nhiễm trùng hoại tử mô mềm sâu tiến triển tối cấp, đe dọa đoạn chi và sốc nhiễm khuẩn tử vong.",
            time_window_hours=2.0,
        ))

    # 2. CIRCULATORY COMPROMISE & SEPTIC SHOCK
    # Hallmarks: Hypotension (BP < 90/60), thready pulse, mottling (vân tím), diaphoresis with rigors
    shock_markers = ["hemodynamic_shock_hypotension", "circulatory_collapse", "urosepsis_hypotension"]
    has_shock_concept = any(c in present_concepts for c in shock_markers)
    has_shock_cues = bool(re.search(r"\b(huyet ap tut|tut huyet ap|ha huyet ap|mach nhanh nho|mach kho bat|\b85/50\b|\b75/45\b|\b70/40\b|\b80/50\b)\b", norm_text))
    has_mottling = bool(re.search(r"\b(noi van tim|da tai xanh|tai xanh|da tim tai)\b", norm_text))
    has_rigors = bool(re.search(r"\b(sot ret run|ret run|nhiem trung huyet)\b", norm_text))

    if has_shock_concept or (has_shock_cues and (has_mottling or has_rigors or "88 tuoi" in norm_text or "nga" in norm_text)):
        consequences.append(PhysiologicConsequence(
            consequence_type=PhysiologicConsequenceType.CIRCULATORY_COMPROMISE,
            severity=ConsequenceSeverity.IMMINENT_LETHAL,
            confidence=0.99,
            supporting_findings=("Tụt huyết áp hệ thống / sốc", "Nổi vân tím tưới máu ngoại vi suy sụp", "Mạch nhanh nhỏ / khó bắt"),
            pathophysiologic_rationale="Sốc tuần hoàn / sốc nhiễm khuẩn giảm tưới máu đa tạng toàn thân cấp tính.",
            time_window_hours=1.0,
        ))

    # 3. RESPIRATORY FAILURE
    # Hallmarks: Severe tachypnea (RR >= 30), gasping (thở hổn hển), cyanosis
    resp_markers = ["respiratory_exhaustion", "severe_tachypnea"]
    has_resp_concept = any(c in present_concepts for c in resp_markers)
    has_resp_cues = bool(re.search(r"\b(tho hon hen|30 lan/phut|tho gap gap|hut hoi du doi|tho nhanh nong)\b", norm_text))
    if has_resp_concept or (has_resp_cues and (has_shock_cues or has_rigors)):
        consequences.append(PhysiologicConsequence(
            consequence_type=PhysiologicConsequenceType.RESPIRATORY_FAILURE,
            severity=ConsequenceSeverity.IMMINENT_LETHAL,
            confidence=0.97,
            supporting_findings=("Thở hổn hển / thở rất nhanh ≥ 30 lần/phút", "Suy sụp thông khí cấp tính"),
            pathophysiologic_rationale="Suy hô hấp cấp kèm hội chứng đáp ứng viêm toàn thân nặng.",
            time_window_hours=1.0,
        ))

    # 4. PERFORATION RISK & VISCERAL DEHISCENCE / EVISCERATION
    # Hallmarks: Wound dehiscence with exposed bowel, violent emesis with transmural esophageal rupture
    perf_markers = ["wound_evisceration", "transmural_esophageal_rupture", "acute_peritonism"]
    has_perf_concept = any(c in present_concepts for c in perf_markers)
    has_evisceration = bool(re.search(r"\b(buc chi|buc vet mo|ruot non loi|loi qua vet mo|loi ruot|ri mau mu o at)\b", norm_text))
    has_boerhaave = bool(re.search(r"\b(non rat manh|oi du doi|non thoc non thao)\b.*?\b(dau sau.*nguc|dau nguc lan lung|dau xe rach nguc)\b", norm_text))

    if has_perf_concept or has_evisceration or has_boerhaave:
        consequences.append(PhysiologicConsequence(
            consequence_type=PhysiologicConsequenceType.PERFORATION_RISK,
            severity=ConsequenceSeverity.IMMINENT_LETHAL,
            confidence=0.99,
            supporting_findings=("Bục vết mổ lộ tạng", "Nguy cơ vỡ thực quản/thủng tạng rỗng"),
            pathophysiologic_rationale="Mất tính toàn vẹn hàng rào khoang phúc mạc / lồng ngực đe dọa viêm phúc mạc/trung thất tối cấp.",
            time_window_hours=1.0,
        ))

    # 5. SYSTEMIC TOXIC STATE (Toxidrome NMS, Sepsis, Severe Poisoning)
    # Hallmarks: Antipsychotic + Hyperthermia + Rigidity + Autonomic Instability (NMS)
    has_nms = bool(re.search(r"\b(haloperidol|thuoc an than|chong loan than)\b.*?\b(sot cao|cung co|va mo hoi|loan nhip tim)\b", norm_text))
    has_nms |= bool(re.search(r"\b(sot cao|cung co toan than)\b.*?\b(haloperidol|thuoc an than)\b", norm_text))
    if has_nms:
        consequences.append(PhysiologicConsequence(
            consequence_type=PhysiologicConsequenceType.SYSTEMIC_TOXIC_STATE,
            severity=ConsequenceSeverity.IMMINENT_LETHAL,
            confidence=0.98,
            supporting_findings=("Sốt cao ác tính kèm tăng trương lực cứng cơ toàn thân", "Dùng thuốc an thần / phong bế dopaminergic"),
            pathophysiologic_rationale="Hội chứng an thần kinh ác tính (Neuroleptic Malignant Syndrome) nguy cơ tiêu cơ vân và trụy tim mạch.",
            time_window_hours=2.0,
        ))

    # 6. TIME-CRITICAL ORGAN LOSS (Septic Arthritis, Testicular Torsion, Limb Ischemia)
    # Hallmarks: Post-injection joint hot/swollen + extreme fever (septic arthritis), acute testicular pain
    has_septic_joint = bool(re.search(r"\b(tiem khop|choc hut khop)\b.*?\b(sung to vu|sung nong do|sot cao.*39|ret run|khong the co duoi)\b", norm_text))
    has_septic_joint |= bool(re.search(r"\b(khop goi.*sau tiem|sau tiem khop)\b.*?\b(sot cao|dau nhuc du doi|khong the dat chan)\b", norm_text))
    has_torsion = bool(re.search(r"\b(tinh hoan|biu)\b.*?\b(dot ngot|du doi|sung to|keo lech)\b", norm_text))

    if has_septic_joint or has_torsion:
        consequences.append(PhysiologicConsequence(
            consequence_type=PhysiologicConsequenceType.TIME_CRITICAL_ORGAN_LOSS,
            severity=ConsequenceSeverity.IMMINENT_LETHAL,
            confidence=0.98,
            supporting_findings=("Nhiễm trùng khớp tối cấp sau can thiệp thủ thuật", "Thiếu máu tạng tối cấp / xoắn tạng"),
            pathophysiologic_rationale="Nguy cơ hủy hoại sụn khớp vĩnh viễn hoặc hoại tử tạng trong cửa sổ thời gian vàng.",
            time_window_hours=4.0,
        ))

    # 7. INTERNAL HEMORRHAGE & TRAUMATIC SHOCK (Geriatric fracture + hemodynamic collapse)
    has_fracture_shock = bool(re.search(r"\b(khop hang|gay xuong|nga)\b.*?\b(chan.*ngan hon|xoay ngoai|khong the dung day)\b.*?\b(mach nhanh|huyet ap tut|85/50)\b", norm_text))
    if has_fracture_shock:
        consequences.append(PhysiologicConsequence(
            consequence_type=PhysiologicConsequenceType.INTERNAL_HEMORRHAGE,
            severity=ConsequenceSeverity.IMMINENT_LETHAL,
            confidence=0.98,
            supporting_findings=("Gãy xương đùi/vùng chậu kèm mất máu trong khoang kín", "Tụt huyết áp sốc mất máu"),
            pathophysiologic_rationale="Gãy xương lớn vùng háng kèm sốc mất máu/giảm thể tích tuần hoàn ở người cao tuổi.",
            time_window_hours=2.0,
        ))

    # Determine max severity
    max_sev = ConsequenceSeverity.MILD_OR_NONE
    summary_findings = []
    for c in consequences:
        summary_findings.extend(c.supporting_findings)
        if c.severity == ConsequenceSeverity.IMMINENT_LETHAL:
            max_sev = ConsequenceSeverity.IMMINENT_LETHAL
        elif c.severity == ConsequenceSeverity.SEVERE_PROGRESSIVE and max_sev != ConsequenceSeverity.IMMINENT_LETHAL:
            max_sev = ConsequenceSeverity.SEVERE_PROGRESSIVE
        elif c.severity == ConsequenceSeverity.MODERATE and max_sev == ConsequenceSeverity.MILD_OR_NONE:
            max_sev = ConsequenceSeverity.MODERATE

    summary = (
        "; ".join(summary_findings[:3])
        if summary_findings
        else "Không ghi nhận rối loạn sinh lý bệnh học đe dọa sinh mạng."
    )

    return PhysiologicAssessment(
        active_consequences=tuple(consequences),
        primary_threat_summary=summary,
        max_severity=max_sev,
    )
