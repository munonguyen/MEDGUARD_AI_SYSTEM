"""Semantic Abstraction Lattice for MedGuard AI Candidate V9.

Projects relational clinical graphs onto higher-order physiologic threat archetypes,
providing robust invariance across linguistic paraphrases and context differentiation
(e.g., distinguishing ischemic chest pressure from reproducible chest wall soreness).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence

from app.services.semantic_relation_extractor import (
    ExtractedConcept,
    RelationType,
    SemanticRelationGraph,
)


class AbstractThreatArchetype(str, Enum):
    LOSS_OF_PERFUSION = "loss_of_perfusion"
    CARDIOPULMONARY_THREAT = "cardiopulmonary_threat"
    CEREBROVASCULAR_CATASTROPHE = "cerebrovascular_catastrophe"
    ACUTE_SURGICAL_ABDOMEN = "acute_surgical_abdomen"
    ACUTE_AIRWAY_ANAPHYLAXIS = "acute_airway_anaphylaxis"
    INTRACRANIAL_HEMORRHAGE_THREAT = "intracranial_hemorrhage_threat"
    HIGH_RISK_SYNCOPE = "high_risk_syncope"
    SYSTEMIC_TOXIC_STATE = "systemic_toxic_state"
    SHOCK = "shock"
    RESPIRATORY_FAILURE = "respiratory_failure"
    OCCULT_ABDOMINAL_ISCHEMIA = "occult_abdominal_ischemia"
    PERFORATION_PATTERN = "perforation_pattern"
    DEEP_INFECTION = "deep_infection"
    PREGNANCY_EMERGENCY = "pregnancy_emergency"
    ACUTE_VISUAL_LOSS = "acute_visual_loss"
    MAJOR_BLEEDING = "major_bleeding"
    METABOLIC_CRISIS = "metabolic_crisis"
    # Benign context exclusions
    BENIGN_MUSCULOSKELETAL_CHEST = "benign_musculoskeletal_chest"
    BENIGN_VASOVAGAL_SYNCOPE = "benign_vasovagal_syncope"
    BENIGN_DENTAL_FACIAL_NUMBNESS = "benign_dental_facial_numbness"
    BENIGN_WORKOUT_SORENESS = "benign_workout_soreness"
    BENIGN_ENVIRONMENTAL_COLD = "benign_environmental_cold"
    BENIGN_CHRONIC_VISUAL_OR_EYESTRAIN = "benign_chronic_visual_or_eyestrain"
    BENIGN_FUNCTIONAL_DYSPEPSIA = "benign_functional_dyspepsia"
    BENIGN_TENSION_HEADACHE = "benign_tension_headache"
    NON_THREATENING_OBSERVATION = "non_threatening_observation"


@dataclass(frozen=True)
class AbstractionPattern:
    archetype: AbstractThreatArchetype
    is_emergency: bool
    confidence: float
    grounding_concepts: list[str]
    clinical_rationale: str
    is_benign_exclusion: bool = False


@dataclass(frozen=True)
class LatticeEvaluationResult:
    active_archetypes: list[AbstractionPattern]
    has_emergency_threat: bool
    has_benign_override: bool
    dominant_threat: AbstractionPattern | None
    threat_summary: str


def evaluate_abstraction_lattice(graph: SemanticRelationGraph) -> LatticeEvaluationResult:
    """Project the relational semantic graph onto the physiologic threat lattice."""
    import re
    patterns: list[AbstractionPattern] = []
    norm = graph.normalized_text

    # Benign context flags
    has_dental = bool(re.search(r"\b(nha khoa|nho rang|tiem te|thuoc te|tram rang|boc rang)\b", norm))
    has_workout = bool(re.search(r"\b(tap ta|hit dat|gym|workout|chay bo|bong da|tap the duc|moi co sau tap|be vac|don dep|lao dong|khuan vac|mang vac|lam viec nang)\b", norm))
    has_eyestrain = bool(re.search(r"\b(kinh ban|bui bay vao|nhin man hinh|nhin may tinh|moi mat|chua lau kinh|duc thuy tinh the lau nam|nhieu nam nay|nhieu thang nay)\b", norm))
    has_ac_cold = bool(re.search(r"\b(ngoi phong dieu hoa|may lanh|troi lanh|quen di tat|di mua|thoi tiet lanh)\b", norm))
    has_postprandial = bool(re.search(r"\b(an no|buffet|day bung|chuong bung|lam ram)\b", norm))
    # Context such as sleep deprivation or computer work is not a symptom.
    # Only create a benign tension-headache abstraction when a headache/head-location
    # symptom is actually present in the user's text.
    has_headache_symptom = bool(re.search(
        r"\b(dau dau|nhuc dau|nang dau|dau thai duong|thai duong.*?dau|dau.*?thai duong)\b",
        norm,
    ))
    has_stress_headache = has_headache_symptom and bool(
        re.search(r"\b(cang thang cong viec|thieu ngu|ngoi may tinh|am i hai ben)\b", norm)
    )

    # -------------------------------------------------------------------------
    # 1. Context Differentiation: Musculoskeletal Chest vs Cardiopulmonary
    # -------------------------------------------------------------------------
    has_chest_pressure = graph.has_concept("chest_pressure")
    has_reproducible_wall = graph.has_concept("reproducible_chest_wall_pain")
    has_diaphoresis = graph.has_concept("diaphoresis")
    has_radiation = graph.has_concept("radiation_to_arm_or_jaw")
    has_dyspnea = graph.has_concept("severe_dyspnea")
    has_exertion = graph.has_concept("exertion_trigger")
    has_syncope = graph.has_concept("syncope")

    has_fleeting = bool(
        ("nguc" in norm or "nhoi nguc" in norm or "dau nguc" in norm or "tuc nguc" in norm)
        and re.search(r"\b(?:2|3|vai)\s*(?:giay|s)\b", norm)
        and any(w in norm for w in ("giay", "roi het", "thoang qua"))
        and not any(w in norm for w in ("dau dau", "goc dau", "dinh dau", "sau gay", "bua ta", "bua bo", "set danh", "chua tung co", "du doi nhat"))
    )

    if (has_reproducible_wall or has_fleeting) and not (has_diaphoresis or has_radiation or has_dyspnea):
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.BENIGN_MUSCULOSKELETAL_CHEST,
                is_emergency=False,
                confidence=0.96,
                grounding_concepts=["reproducible_chest_wall_pain" if has_reproducible_wall else "fleeting_chest_pain"],
                clinical_rationale="Cơn đau nhói ngực thoáng qua vài giây hoặc đau cơ thành ngực tái lập khi ấn; không có dấu hiệu tự chủ hay lan tỏa.",
                is_benign_exclusion=True,
            )
        )
    elif has_chest_pressure and (has_diaphoresis or has_radiation or has_dyspnea or has_exertion):
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.CARDIOPULMONARY_THREAT,
                is_emergency=True,
                confidence=0.98,
                grounding_concepts=["chest_pressure", "autonomic_or_ischemic_features"],
                clinical_rationale="Hội chứng đè nghẹt ngực cấp kèm triệu chứng thần kinh tự chủ hoặc lan tỏa (nghi thiếu máu cơ tim/ACS).",
            )
        )

    # -------------------------------------------------------------------------
    # 2. Vascular / Limb Ischemia (Loss of Perfusion) vs Environmental Cold
    # -------------------------------------------------------------------------
    has_cold = graph.has_concept("cold_extremity")
    has_pallor = graph.has_concept("pallor_or_cyanosis")
    has_absent_pulse = graph.has_concept("absent_or_weak_pulse")

    if has_ac_cold and has_cold and not has_absent_pulse:
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.BENIGN_ENVIRONMENTAL_COLD,
                is_emergency=False,
                confidence=0.95,
                grounding_concepts=["cold_extremity"],
                clinical_rationale="Chi lạnh do co mạch sinh lý khi ở phòng điều hòa hoặc thời tiết lạnh; không mất mạch.",
                is_benign_exclusion=True,
            )
        )
    elif (has_cold and has_pallor) or (has_cold and has_absent_pulse) or (has_pallor and has_absent_pulse):
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.LOSS_OF_PERFUSION,
                is_emergency=True,
                confidence=0.98,
                grounding_concepts=["cold_extremity", "pallor_or_pulse_deficit"],
                clinical_rationale="Hội chứng mất tưới máu chi cấp (Acute Limb Ischemia: lạnh buốt, trắng bệch hoặc mất mạch).",
            )
        )

    # -------------------------------------------------------------------------
    # 3. Cerebrovascular Catastrophe vs Benign Mimics (Dental / Workout / Eyestrain)
    # -------------------------------------------------------------------------
    has_weakness = graph.has_concept("focal_weakness")
    has_facial = graph.has_concept("facial_droop_or_numbness")
    has_speech = graph.has_concept("speech_impairment")
    has_vision = graph.has_concept("visual_loss_acute")

    has_airway_or_neck = bool(re.search(r"\b(kho tho|tho rit|chay dai|san mieng|luoi|day loi|phu ne|suy ho hap|khong nuot duoc|kho nuot)\b", norm))

    if has_dental and (has_facial or has_speech) and not has_airway_or_neck:
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.BENIGN_DENTAL_FACIAL_NUMBNESS,
                is_emergency=False,
                confidence=0.96,
                grounding_concepts=["facial_droop_or_numbness"],
                clinical_rationale="Tê rần khóe miệng hoặc méo tạm thời sau can thiệp nha khoa tiêm thuốc tê.",
                is_benign_exclusion=True,
            )
        )
    elif has_workout and has_weakness:
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.BENIGN_WORKOUT_SORENESS,
                is_emergency=False,
                confidence=0.95,
                grounding_concepts=["focal_weakness"],
                clinical_rationale="Mỏi cơ sinh lý sau vận động thể lực nặng/tập tạ/lao động (DOMS).",
                is_benign_exclusion=True,
            )
        )
    elif has_eyestrain and has_vision:
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.BENIGN_CHRONIC_VISUAL_OR_EYESTRAIN,
                is_emergency=False,
                confidence=0.94,
                grounding_concepts=["visual_loss_acute"],
                clinical_rationale="Mờ mắt do mỏi mắt điều tiết, kính bẩn hoặc đục thủy tinh thể mạn tính.",
                is_benign_exclusion=True,
            )
        )
    elif has_weakness or has_facial or has_speech or has_vision:
        groundings = []
        if has_weakness: groundings.append("focal_weakness")
        if has_facial: groundings.append("facial_droop_or_numbness")
        if has_speech: groundings.append("speech_impairment")
        if has_vision: groundings.append("visual_loss_acute")

        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.CEREBROVASCULAR_CATASTROPHE,
                is_emergency=True,
                confidence=0.99,
                grounding_concepts=groundings,
                clinical_rationale="Dấu hiệu khiếm khuyết thần kinh khu trú cấp tính (nghi đột quỵ não / TIA / mất tưới máu võng mạc).",
            )
        )

    # -------------------------------------------------------------------------
    # 4. Acute Surgical Abdomen / Perforation vs Functional Dyspepsia
    # -------------------------------------------------------------------------
    has_abdo = graph.has_concept("abdominal_pain_severe")
    has_rigid = bool(re.search(r"\b(?:cung\s+nhu\s+go|cung\s+nhu\s+da|nhu\s+khuc\s+go|nhu\s+tam\s+van|nhu\s+mieng\s+van|cung\s+ngac|cung\s+do|gong\s+cung|co\s+cung|de\s+khang|thung\s+tang\s+rong|viem\s+phuc\s+mac|nhu\s+dao\s+dam|coc\s+go)\b", norm))

    has_agony = bool(re.search(r"\b(gap nguoi om bung|lan lon|bop nghet|xoan lai|quan that|chet di song lai|dau quan quai)\b", norm))
    has_acute_onset = graph.has_concept("acute_onset") or bool(re.search(r"\b(moi bi|dot ngot|vua moi|luc nay)\b", norm))
    has_obstetric = graph.has_concept("obstetric_acute_abdomen") or bool(
        ("tre kinh" in norm or "cham kinh" in norm or "mang thai" in norm) and ("dau bung" in norm or "dau ho chau" in norm)
    )

    if has_postprandial and has_abdo and not has_rigid:
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.BENIGN_FUNCTIONAL_DYSPEPSIA,
                is_emergency=False,
                confidence=0.93,
                grounding_concepts=["abdominal_pain_severe"],
                clinical_rationale="Đầy bụng tức nhẹ sau khi ăn no tiệc buffet; không có co cứng thành bụng.",
                is_benign_exclusion=True,
            )
        )
    elif has_obstetric and (has_syncope or has_diaphoresis or bool(re.search(r"\b(choang vang|chong mat|ngat|xuat huyet|chay mau)\b", norm))):
        # Patient-facing rationale must only assert features present in the input.
        # Differential diagnoses may be named as possibilities, but rule antecedents
        # that were not observed must never be rewritten as patient facts.
        obstetric_evidence: list[str] = []
        if re.search(r"\b(mang thai|co bau|san phu)\b", norm):
            obstetric_evidence.append("đang mang thai")
        elif re.search(r"\b(tre kinh|cham kinh)\b", norm):
            obstetric_evidence.append("trễ/chậm kinh")
        if re.search(r"\b(dau bung|dau ho chau)\b", norm):
            obstetric_evidence.append("đau bụng/đau hố chậu")
        if re.search(r"\b(xuat huyet|chay mau)\b", norm):
            obstetric_evidence.append("chảy máu")
        if has_syncope or re.search(r"\b(choang vang|chong mat|ngat)\b", norm):
            obstetric_evidence.append("choáng/ngất")
        if has_diaphoresis:
            obstetric_evidence.append("vã mồ hôi/dấu hiệu tuần hoàn")
        evidence_text = ", ".join(dict.fromkeys(obstetric_evidence)) or "dấu hiệu sản khoa cấp"
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.PREGNANCY_EMERGENCY,
                is_emergency=True,
                confidence=0.99,
                grounding_concepts=["obstetric_acute_abdomen", "hemodynamic_compromise"],
                clinical_rationale=(
                    f"Nhóm dấu hiệu sản khoa cấp ({evidence_text}) cần được đánh giá khẩn để "
                    "loại trừ nguyên nhân nguy hiểm như thai ngoài tử cung hoặc chảy máu sản khoa."
                ),
            )
        )
    elif has_abdo and (has_diaphoresis or has_pallor or has_rigid or (has_agony and has_acute_onset)):
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.ACUTE_SURGICAL_ABDOMEN,
                is_emergency=True,
                confidence=0.98,
                grounding_concepts=["abdominal_pain_severe"],
                clinical_rationale="Hội chứng bụng ngoại khoa cấp (Đau dữ dội kèm co cứng thành bụng hoặc đau quặn thắt xoắn vặn lăn lộn/phản ứng sốc).",
            )
        )

    # -------------------------------------------------------------------------
    # 5. Acute Airway Anaphylaxis & Respiratory Failure / Ludwig's Angina
    # -------------------------------------------------------------------------
    has_angioedema = graph.has_concept("angioedema_or_stridor")
    has_resp_fail = bool(re.search(r"\b(suy ho hap|tho ren ri|co keo hom uc|tho rit ron nguoi|tim tai moi dau chi|khong the noi duoc ca cau)\b", norm))
    has_ludwig = bool(re.search(r"\b(san mieng|duoi cam|day loi|luoi bi day loi|chay dai.*?kho tho|kho tho.*?chay dai|ludwig|viem tay san mieng)\b", norm))

    if has_angioedema or has_resp_fail or has_ludwig:
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.ACUTE_AIRWAY_ANAPHYLAXIS,
                is_emergency=True,
                confidence=0.99,
                grounding_concepts=["airway_compromise"],
                clinical_rationale="Phù nề đường thở cấp, nhiễm trùng sàn miệng (Ludwig's) hoặc suy hô hấp nặng (nguy cơ tắc nghẽn tối khẩn).",
            )
        )

    # -------------------------------------------------------------------------
    # 6. Thunderclap Headache vs Tension / Cold-Stimulus Headache
    # -------------------------------------------------------------------------
    has_thunderclap = graph.has_concept("thunderclap_headache") or bool(
        re.search(r"\b(du doi nhat tu truoc den nay|tang cuc manh trong vai giay|chua tung co trong doi.*?vai giay|nhu bua ta dap.*?vai giay|buot nhoi dinh dau.*?dot ngot)\b", norm)
    )
    has_cold_trigger = bool(
        re.search(r"\b(kem lanh|an kem|can mieng kem|da bao|nuoc da|do lanh|uong nuoc da|que kem)\b", norm)
        or ("kem" in graph.raw_text.lower() and "kèm" not in graph.raw_text.lower() and re.search(r"\b(an|can|mut|uong)\b", norm))
    )
    has_meningitis_signs = bool(re.search(r"\b(sot|cung co|not tim|ban xuat huyet|tu ban|hon me)\b", norm))
    has_brain_freeze = has_cold_trigger and not has_meningitis_signs and bool(re.search(r"\b(giay|tu het|het hoan toan|bien mat|thoang qua)\b", norm)) and not ("khong bien mat" in norm or "khong het" in norm)

    if has_brain_freeze:
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.BENIGN_TENSION_HEADACHE,
                is_emergency=False,
                confidence=0.98,
                grounding_concepts=["cold_stimulus_headache"],
                clinical_rationale="Cơn đau buốt đầu thoáng qua vài chục giây sau khi ăn kem/đồ lạnh (brain freeze) là phản ứng sinh lý lành tính.",
                is_benign_exclusion=True,
            )
        )
    elif has_stress_headache and not bool(re.search(r"\b(set danh|bua bo|du doi dot ngot)\b", norm)):
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.BENIGN_TENSION_HEADACHE,
                is_emergency=False,
                confidence=0.92,
                grounding_concepts=["tension_headache"],
                clinical_rationale="Đau đầu âm ỉ do căng thẳng công việc và thiếu ngủ, không có dấu hiệu khởi phát sét đánh.",
                is_benign_exclusion=True,
            )
        )
    elif has_thunderclap:
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.INTRACRANIAL_HEMORRHAGE_THREAT,
                is_emergency=True,
                confidence=0.98,
                grounding_concepts=["thunderclap_headache"],
                clinical_rationale="Đau đầu dữ dội khởi phát sét đánh (nghi xuất huyết dưới nhện).",
            )
        )

    # -------------------------------------------------------------------------
    # 7. High-Risk Syncope vs Benign Micturition Syncope
    # -------------------------------------------------------------------------
    has_syncope = graph.has_concept("syncope")
    has_micturition = graph.has_concept("micturition_syncope")
    has_bleeding_or_shock = bool(re.search(r"\b(ra mau|phan den|xuat huyet|chay mau|non ra mau|tieu ra mau)\b", norm))

    if has_micturition and not (has_chest_pressure or has_dyspnea or has_weakness or has_diaphoresis or has_bleeding_or_shock):
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.BENIGN_VASOVAGAL_SYNCOPE,
                is_emergency=False,
                confidence=0.94,
                grounding_concepts=["micturition_syncope"],
                clinical_rationale="Ngất phế vị phản xạ khi đi tiểu đơn thuần; không có triệu chứng tim mạch, thần kinh hoặc vã mồ hôi/sốc đi kèm.",
                is_benign_exclusion=True,
            )
        )
    elif has_syncope and (has_exertion or has_chest_pressure or has_dyspnea or has_diaphoresis or ("hoa mat" in norm and not has_micturition)):
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.HIGH_RISK_SYNCOPE,
                is_emergency=True,
                confidence=0.98,
                grounding_concepts=["syncope"],
                clinical_rationale="Ngất xỉu nguy cơ cao kèm triệu chứng gắng sức, đau ngực, khó thở hoặc dấu hiệu sốc suy sụp tuần hoàn (toát mồ hôi hột).",
            )
        )

    # -------------------------------------------------------------------------
    # 8. Toxic Exposure & Systemic Toxidrome Signature
    # -------------------------------------------------------------------------
    from app.services.toxicology_signature_router import route_by_toxicity_signature
    tox_sig = route_by_toxicity_signature(graph.raw_text)
    if tox_sig.is_emergency_toxidrome:
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.SYSTEMIC_TOXIC_STATE,
                is_emergency=True,
                confidence=tox_sig.confidence,
                grounding_concepts=[str(d.value) for d in tox_sig.matched_dimensions],
                clinical_rationale=tox_sig.rationale,
            )
        )

    # -------------------------------------------------------------------------
    # 9. Metabolic Crisis / DKA / Hypoglycemic Coma
    # -------------------------------------------------------------------------
    has_metabolic = bool(re.search(r"\b(kussmaul|tho nhanh sau|mui tao thoi|toan chuyen hoa|tieu duong.*?hon me|ha duong huyet.*?hon me)\b", norm))
    if has_metabolic:
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.METABOLIC_CRISIS,
                is_emergency=True,
                confidence=0.98,
                grounding_concepts=["metabolic_crisis"],
                clinical_rationale="Khủng hoảng chuyển hóa cấp tính (nghi nhiễm toan ceton đái tháo đường DKA hoặc hôn mê hạ đường huyết).",
            )
        )

    # -------------------------------------------------------------------------
    # 10. Major Bleeding / Anticoagulant Hemorrhage
    # -------------------------------------------------------------------------
    has_major_bleed = bool(re.search(r"\b(non ra mau|di ngoai phan den|di tieu ra mau|tieu ra mau|ra mau do|chay mau o at|thau mau do tuoi|phan den nhu ba ca phe)\b", norm))
    has_coag_bleed = graph.has_concept("coagulopathy_hemorrhage") or bool(
        ("warfarin" in norm or "thuoc chong dong" in norm) and
        ("chay mau" in norm or "bam tim" in norm or "xuat huyet" in norm)
    )
    if has_major_bleed or has_coag_bleed:
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.MAJOR_BLEEDING,
                is_emergency=True,
                confidence=0.98,
                grounding_concepts=["major_bleeding" if has_major_bleed else "coagulopathy_hemorrhage"],
                clinical_rationale="Xuất huyết tự phát lớn hoặc quá liều thuốc chống đông đe dọa mất máu và sốc tuần hoàn.",
            )
        )

    # -------------------------------------------------------------------------
    # 11. Cauda Equina Syndrome / Acute Spinal Cord Compression
    # -------------------------------------------------------------------------
    has_cauda = graph.has_concept("cauda_equina_signs") or bool(
        ("that lung" in norm or "dau lung" in norm) and
        ("hai chan" in norm or "2 chan" in norm) and
        ("hau mon" in norm or "yen ngua" in norm)
    )
    if has_cauda:
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.CEREBROVASCULAR_CATASTROPHE,
                is_emergency=True,
                confidence=0.99,
                grounding_concepts=["cauda_equina_signs"],
                clinical_rationale="Hội chứng chùm đuôi ngựa cấp tính (đau thắt lưng lan hai chân kèm tê vùng quanh hậu môn/yên ngựa). Cần giải ép khẩn cấp.",
            )
        )

    # -------------------------------------------------------------------------
    # 11. Pregnancy Emergency (Severe Pre-eclampsia / Eclampsia)
    # -------------------------------------------------------------------------
    has_preg_flag = bool(re.search(r"\b(mang thai|san phu|co bau|thai \d+ tuan)\b", norm))
    has_eclamptic = bool(re.search(r"\b(co giat|nhin mo|dau dau du doi|tien san giat|san giat)\b", norm))
    if has_preg_flag and has_eclamptic:
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.PREGNANCY_EMERGENCY,
                is_emergency=True,
                confidence=0.99,
                grounding_concepts=["pregnancy_emergency"],
                clinical_rationale="Cấp cứu sản khoa đe dọa tính mạng mẹ và thai nhi (nghi tiền sản giật nặng / sản giật).",
            )
        )

    # -------------------------------------------------------------------------
    # 12. Circulatory Shock / Hypotension Collapse
    # -------------------------------------------------------------------------
    has_shock = bool(re.search(r"\b(tut huyet ap|truy mach|ha huyet ap|soc nhiem khuan|soc mat mau|soc tim|mach nhanh nho|mach kho bat|choang vang.*?nga quy|nga quy)\b", norm))
    has_shock_signs = graph.has_concept("cold_extremity") or graph.has_concept("pallor_or_cyanosis") or graph.has_concept("syncope") or "lanh ngat" in norm or "truy mach" in norm or "tut huyet ap" in norm
    if has_shock and has_shock_signs:
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.SHOCK,
                is_emergency=True,
                confidence=0.99,
                grounding_concepts=["shock", "hypotension"],
                clinical_rationale="Sốc tuần hoàn / trụy mạch cấp tính đe dọa ngừng tim.",
            )
        )

    # -------------------------------------------------------------------------
    # 13. Deep Infection / Sepsis / Meningitis
    # -------------------------------------------------------------------------
    has_deep_inf = bool(re.search(r"\b(sot cao.*?ret run|sot cao 40|sot.*?40 do|nhiem trung huyet|sepsis|viem mang nao|thop phong|lo mo lu lan.*?sot|da noi van hoa|sot.*?cung co|cung co.*?sot|not tim.*?khong bien mat|ban xuat huyet|tu ban|xuat huyet duoi da.*?sot)\b", norm))
    if has_deep_inf:
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.DEEP_INFECTION,
                is_emergency=True,
                confidence=0.98,
                grounding_concepts=["deep_infection", "severe_systemic_infection"],
                clinical_rationale="Hội chứng nhiễm trùng nhiễm độc toàn thân nặng (nghi nhiễm trùng huyết hoặc viêm màng não).",
            )
        )

    # -------------------------------------------------------------------------
    # 14. Occult Abdominal Ischemia
    # -------------------------------------------------------------------------
    has_mesenteric = bool(re.search(r"\b(vuot qua muc|khong tuong xung|thieu mau mac treo|tac dong mach mac treo)\b", norm)) or ("dau bung du doi" in norm and ("lanh" in norm or "tut huyet ap" in norm))
    if has_mesenteric and has_abdo:
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.OCCULT_ABDOMINAL_ISCHEMIA,
                is_emergency=True,
                confidence=0.98,
                grounding_concepts=["abdominal_pain_severe", "mesenteric_threat"],
                clinical_rationale="Thiếu máu mạc treo cấp / đau bụng dữ dội không tương xứng dấu hiệu thực thể.",
            )
        )

    # -------------------------------------------------------------------------
    # 15. Perforation Pattern
    # -------------------------------------------------------------------------
    if has_rigid and has_abdo:
        patterns.append(
            AbstractionPattern(
                archetype=AbstractThreatArchetype.PERFORATION_PATTERN,
                is_emergency=True,
                confidence=0.99,
                grounding_concepts=["abdominal_pain_severe", "peritoneal_rigidity"],
                clinical_rationale="Hội chứng thủng tạng rỗng / viêm phúc mạc toàn thể với thành bụng co cứng như gỗ.",
            )
        )

    emergency_patterns = [p for p in patterns if p.is_emergency]
    has_emergency = bool(emergency_patterns)
    has_benign = any(p.is_benign_exclusion for p in patterns)

    dominant = emergency_patterns[0] if emergency_patterns else (patterns[0] if patterns else None)
    summary = dominant.clinical_rationale if dominant else "Không phát hiện hình thái đe dọa sinh lý cấp tính."

    return LatticeEvaluationResult(
        active_archetypes=patterns,
        has_emergency_threat=has_emergency,
        has_benign_override=has_benign and not has_emergency,
        dominant_threat=dominant,
        threat_summary=summary,
    )
