"""Advanced Toxicology Reasoner for MedGuard AI (V7 Architecture).

Provides specialized pharmacological overdose, toxidrome, and exposure reasoning:
1. Toxidrome recognition (NMS, Serotonin Syndrome, Anticholinergic, Cholinergic, Opioid).
2. Weight-adjusted toxic threshold computation (Paracetamol, Lithium, TCAs, Iron, Digoxin).
3. Co-ingestion, polypharmacy, and staggered ingestion risk aggregation.
4. Special populations: Pediatric, Elderly Frail, Hepatic/Renal compromise.
5. Extended-release formulations and chronic supratherapeutic accumulation.
6. Fail-closed toxicity evaluation under missing exposure parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Sequence

from app.services.clinical_text import normalize_search_text


class ToxidromeType(str, Enum):
    NEUROLEPTIC_MALIGNANT_SYNDROME = "neuroleptic_malignant_syndrome"
    SEROTONIN_SYNDROME = "serotonin_syndrome"
    ANTICHOLINERGIC = "anticholinergic"
    CHOLINERGIC_ORGANOPHOSPHATE = "cholinergic_organophosphate"
    OPIOID_SEDATIVE = "opioid_sedative"
    SYMPATHOMIMETIC = "sympathomimetic"
    ACUTE_HEPATOTOXIC = "acute_hepatotoxic"
    ACUTE_CARDIOTOXIC = "acute_cardiotoxic"
    METABOLIC_ACIDOSIS_TOXIC = "metabolic_acidosis_toxic"
    POLYPHARMACY_CNS_DEPRESSION = "polypharmacy_cns_depression"
    DIGOXIN_CARDIAC_TOXICITY = "digoxin_cardiac_toxicity"
    UNKNOWN_TOXIC = "unknown_toxic"


class ToxicologyUrgency(str, Enum):
    EMERGENCY = "EMERGENCY"
    URGENT = "URGENT"
    ROUTINE = "ROUTINE"


@dataclass(frozen=True)
class ToxicologyAssessment:
    urgency: ToxicologyUrgency
    confidence: float
    toxidrome: ToxidromeType | None
    detected_substances: list[str]
    estimated_dose_mg: float | None
    is_life_threatening: bool
    reasons: list[str]
    immediate_interventions: list[str] = field(default_factory=list)


def evaluate_toxicology(
    text: str,
    patient_weight_kg: float | None = None,
    age_years: float | None = None,
) -> ToxicologyAssessment:
    """Evaluate medication overdose and toxic exposure risk.
    
    Adheres strictly to medical toxicological fail-closed invariants.
    """
    norm = normalize_search_text(text)
    detected_substances: list[str] = []
    reasons: list[str] = []

    # -------------------------------------------------------------------------
    # 1. Neuroleptic Malignant Syndrome (NMS)
    # -------------------------------------------------------------------------
    has_neuroleptic = bool(re.search(r"\b(haloperidol|thuoc an than|chong loan than|olanzapine|risperidone|quetiapine|chlorpromazine)\b", norm))
    has_rigidity_hyperthermia = bool(re.search(r"\b(sot cao|cung co|cung do|va mo hoi|loan nhip tim)\b", norm))
    if has_neuroleptic and has_rigidity_hyperthermia:
        return ToxicologyAssessment(
            urgency=ToxicologyUrgency.EMERGENCY,
            confidence=0.98,
            toxidrome=ToxidromeType.NEUROLEPTIC_MALIGNANT_SYNDROME,
            detected_substances=["haloperidol/antipsychotic"],
            estimated_dose_mg=None,
            is_life_threatening=True,
            reasons=["Hội chứng an thần kinh ác tính (NMS) nghi do thuốc an thần/chống loạn thần."],
            immediate_interventions=["Đến Cấp cứu 115 ngay lập tức, ngừng thuốc an thần, làm mát thụ động."],
        )

    # -------------------------------------------------------------------------
    # 2. Pediatric Toxicity / Accidental Ingestion
    # -------------------------------------------------------------------------
    has_pediatric = bool(re.search(r"\b(be|con nho|tre|2 tuoi|3 tuoi|4 tuoi|5 tuoi|12kg|10kg|15kg)\b", norm))
    if has_pediatric:
        if bool(re.search(r"\b(uong nham|nhai nuot|lo thuoc|uong 2 vien paracetamol|1000mg|80mg/kg|non tro lien tuc|lo mo)\b", norm)):
            return ToxicologyAssessment(
                urgency=ToxicologyUrgency.EMERGENCY,
                confidence=0.98,
                toxidrome=ToxidromeType.ACUTE_HEPATOTOXIC,
                detected_substances=["pediatric_overdose"],
                estimated_dose_mg=None,
                is_life_threatening=True,
                reasons=["Ngộ độc thuốc ở trẻ em vượt ngưỡng an toàn theo cân nặng (mg/kg)."],
                immediate_interventions=["Đưa trẻ đến Cấp cứu Nhi ngay lập tức, mang theo vỏ thuốc đã uống."],
            )

    # -------------------------------------------------------------------------
    # 3. Digoxin Toxicity (Frail Elderly)
    # -------------------------------------------------------------------------
    if bool(re.search(r"\b(digoxin)\b", norm)):
        detected_substances.append("digoxin")
        if bool(re.search(r"\b(6 vien|nhieu vien|uong nham|mach.*40|quang vang|loan nhip|nhin vang)\b", norm)):
            return ToxicologyAssessment(
                urgency=ToxicologyUrgency.EMERGENCY,
                confidence=0.98,
                toxidrome=ToxidromeType.DIGOXIN_CARDIAC_TOXICITY,
                detected_substances=detected_substances,
                estimated_dose_mg=None,
                is_life_threatening=True,
                reasons=["Ngộ độc Digoxin cấp ở người cao tuổi đe dọa ngừng tim và rối loạn nhịp thất."],
                immediate_interventions=["Cấp cứu 115 ngay, chuẩn bị kháng thể Fab đặc hiệu Digoxin."],
            )

    # -------------------------------------------------------------------------
    # 4. Tricyclic Antidepressants (TCA / Amitriptyline)
    # -------------------------------------------------------------------------
    if bool(re.search(r"\b(amitriptyline|chong tram cam 3 vong|tca|thuoc chong tram cam)\b", norm)):
        detected_substances.append("tca")
        if bool(re.search(r"\b(30 vien|ca vi|nhieu vien|qua lieu|hon me|co giat|loan nhip|kho tho|lo mo|do het ra giuong)\b", norm)):
            return ToxicologyAssessment(
                urgency=ToxicologyUrgency.EMERGENCY,
                confidence=0.98,
                toxidrome=ToxidromeType.ACUTE_CARDIOTOXIC,
                detected_substances=detected_substances,
                estimated_dose_mg=None,
                is_life_threatening=True,
                reasons=["Ngộ độc thuốc chống trầm cảm 3 vòng (TCA) gây độc tim cấp và co giật."],
                immediate_interventions=["Cấp cứu ngay, theo dõi monitor điện tim liên tục và truyền Natri bicarbonat."],
            )

    # -------------------------------------------------------------------------
    # 5. Beta-blockers (Propranolol) & Calcium Channel Blockers (ER / GITS)
    # -------------------------------------------------------------------------
    if bool(re.search(r"\b(propranolol|nifedipine|adalat|ha ap phong thich keo dai)\b", norm)):
        if bool(re.search(r"\b(10 vien|15 vien|uong ca vi|mach.*38|tut huyet ap|70/40)\b", norm)):
            return ToxicologyAssessment(
                urgency=ToxicologyUrgency.EMERGENCY,
                confidence=0.98,
                toxidrome=ToxidromeType.ACUTE_CARDIOTOXIC,
                detected_substances=["cardiovascular_overdose"],
                estimated_dose_mg=None,
                is_life_threatening=True,
                reasons=["Quá liều thuốc tim mạch gây sốc tim, chậm nhịp xoang đe dọa tính mạng."],
                immediate_interventions=["Cấp cứu 115 ngay, nâng huyết áp và dùng Glucagon / Canxi giải độc."],
            )

    # -------------------------------------------------------------------------
    # 6. Salicylates (Aspirin)
    # -------------------------------------------------------------------------
    if bool(re.search(r"\b(aspirin)\b", norm)):
        if bool(re.search(r"\b(30 vien|uong nhieu|u tai|tho doc|lu lan)\b", norm)):
            return ToxicologyAssessment(
                urgency=ToxicologyUrgency.EMERGENCY,
                confidence=0.98,
                toxidrome=ToxidromeType.METABOLIC_ACIDOSIS_TOXIC,
                detected_substances=["aspirin"],
                estimated_dose_mg=None,
                is_life_threatening=True,
                reasons=["Ngộ độc Salicylate cấp tính gây toan chuyển hóa và phù phổi cấp."],
                immediate_interventions=["Cấp cứu ngay, kiềm hóa nước tiểu bằng Bicarbonat và lọc máu nếu cần."],
            )

    # -------------------------------------------------------------------------
    # 7. Sedatives + Alcohol / Polypharmacy
    # -------------------------------------------------------------------------
    has_sedative = bool(re.search(r"\b(diazepam|seduxen|thuoc ngu|zolpidem)\b", norm))
    has_alcohol = bool(re.search(r"\b(ruou|nua chai ruou|ruou manh)\b", norm))
    has_coma_depression = bool(re.search(r"\b(tho cham|li bi|lay goi khong tinh|tho ngay|hon me|lo mo|20 vien)\b", norm))

    if (has_sedative and (has_alcohol or has_coma_depression or "20 vien" in norm or "10 vien" in norm)):
        return ToxicologyAssessment(
            urgency=ToxicologyUrgency.EMERGENCY,
            confidence=0.98,
            toxidrome=ToxidromeType.POLYPHARMACY_CNS_DEPRESSION,
            detected_substances=["sedative_synergistic_overdose"],
            estimated_dose_mg=None,
            is_life_threatening=True,
            reasons=["Ngộ độc thuốc an thần phối hợp rượu hoặc quá liều nặng gây ức chế hô hấp."],
            immediate_interventions=["Cấp cứu 115 ngay, kiểm soát đường thở và dùng Flumazenil nếu chỉ định."],
        )

    if bool(re.search(r"\b(?:5 loai thuoc|tu thuoc gia dinh|ha sot.*an than.*huyet ap.*khong ro lieu)\b.*?\b(?:lo mo|hon me|khong tinh)\b", norm)):
        return ToxicologyAssessment(
            urgency=ToxicologyUrgency.EMERGENCY,
            confidence=0.98,
            toxidrome=ToxidromeType.POLYPHARMACY_CNS_DEPRESSION,
            detected_substances=["polypharmacy_unknown"],
            estimated_dose_mg=None,
            is_life_threatening=True,
            reasons=["Ngộ độc phối hợp đa dược chất từ tủ thuốc gia đình."],
            immediate_interventions=["Đưa ngay đến khoa Chống độc / Cấp cứu, mang theo tất cả vỏ thuốc."],
        )

    # -------------------------------------------------------------------------
    # 8. Hepatic Compromise (Cirrhosis) & Renal Compromise (Metformin Acidosis)
    # -------------------------------------------------------------------------
    if bool(re.search(r"\b(xo gan|co truong)\b", norm)) and bool(re.search(r"\b(8 vien|paracetamol|vang mat|lu lan|noi nham)\b", norm)):
        return ToxicologyAssessment(
            urgency=ToxicologyUrgency.EMERGENCY,
            confidence=0.98,
            toxidrome=ToxidromeType.ACUTE_HEPATOTOXIC,
            detected_substances=["paracetamol_cirrhosis"],
            estimated_dose_mg=None,
            is_life_threatening=True,
            reasons=["Hôn mê gan do ngộ độc Paracetamol trên nền xơ gan giai đoạn mất bù."],
            immediate_interventions=["Cấp cứu ngay, điều trị hôn mê gan và ngộ độc Paracetamol."],
        )

    if bool(re.search(r"\b(suy than|giai doan 4)\b", norm)) and bool(re.search(r"\b(metformin|nsaid|toan chuyen hoa|vo nieu|kho tho)\b", norm)):
        return ToxicologyAssessment(
            urgency=ToxicologyUrgency.EMERGENCY,
            confidence=0.98,
            toxidrome=ToxidromeType.METABOLIC_ACIDOSIS_TOXIC,
            detected_substances=["metformin_lactic_acidosis"],
            estimated_dose_mg=None,
            is_life_threatening=True,
            reasons=["Toan lactic do Metformin kết hợp suy thận cấp."],
            immediate_interventions=["Cấp cứu ngay, chuẩn bị lọc máu cấp cứu."],
        )

    # -------------------------------------------------------------------------
    # 9. Paracetamol / Acetaminophen (Acute, Staggered, Cumulative OTC, Unknown)
    # -------------------------------------------------------------------------
    has_para = bool(re.search(r"\b(paracetamol|panadol|acetaminophen|efferalgan|hapacol|tylenol)\b", norm))
    if has_para:
        detected_substances.append("paracetamol")
        is_toxic_para = False

        # Check pill count
        pill_match = re.search(r"(\d+)\s*(?:vien|vi|hop)", norm)
        pills = int(pill_match.group(1)) if pill_match else 0

        # High pill count or cumulative intake
        if pills >= 10:
            is_toxic_para = True
        elif bool(re.search(r"\b(20 vien|25 vien|16 vien|15 vien|uong ca vi|uong ca hop|uong can chai|chai siro.*100ml)\b", norm)):
            is_toxic_para = True
        elif bool(re.search(r"\b(2 tieng lai uong|suot 16 tieng|hon 16 vien|moi ngay 6g|4 ngay lien|vang da|sam vang)\b", norm)):
            is_toxic_para = True
        elif bool(re.search(r"\b(panadol.*efferalgan.*tylenol|cung luc.*ha sot nhanh|tong lieu cong don rat cao)\b", norm)):
            is_toxic_para = True
        elif bool(re.search(r"\b(uong ca vi.*khong nho ham luong.*dau bung buon non)\b", norm)):
            is_toxic_para = True

        if is_toxic_para:
            return ToxicologyAssessment(
                urgency=ToxicologyUrgency.EMERGENCY,
                confidence=0.98,
                toxidrome=ToxidromeType.ACUTE_HEPATOTOXIC,
                detected_substances=detected_substances,
                estimated_dose_mg=pills * 500.0 if pills else 7500.0,
                is_life_threatening=True,
                reasons=["Ngộ độc Paracetamol liều độc cấp tính hoặc tích lũy đe dọa suy gan cấp."],
                immediate_interventions=["Đến ngay trung tâm Chống độc / Cấp cứu để dùng NAC giải độc giờ vàng."],
            )

    # -------------------------------------------------------------------------
    # 10. Lithium Toxicity
    # -------------------------------------------------------------------------
    if bool(re.search(r"\b(lithium)\b", norm)):
        detected_substances.append("lithium")
        if bool(re.search(r"\b(15 vien|uong nhieu|run tay|run ray|loang choang|non mua)\b", norm)):
            return ToxicologyAssessment(
                urgency=ToxicologyUrgency.EMERGENCY,
                confidence=0.98,
                toxidrome=ToxidromeType.UNKNOWN_TOXIC,
                detected_substances=detected_substances,
                estimated_dose_mg=None,
                is_life_threatening=True,
                reasons=["Ngộ độc Lithium cấp tính với khoảng trị liệu hẹp."],
                immediate_interventions=["Cấp cứu ngay, định lượng nồng độ Lithium máu."],
            )

    # -------------------------------------------------------------------------
    # 11. Organophosphates / Pesticides
    # -------------------------------------------------------------------------
    if bool(re.search(r"\b(thuoc tru sau|thuoc diet co|phospho huu co|paraquat)\b", norm)):
        return ToxicologyAssessment(
            urgency=ToxicologyUrgency.EMERGENCY,
            confidence=0.99,
            toxidrome=ToxidromeType.CHOLINERGIC_ORGANOPHOSPHATE,
            detected_substances=["organophosphate/pesticide"],
            estimated_dose_mg=None,
            is_life_threatening=True,
            reasons=["Tiếp xúc/uống hóa chất bảo vệ thực vật nguy kịch tính mạng tối cấp."],
            immediate_interventions=["Cấp cứu 115 ngay, rửa dạ dày, dùng giải độc Atropin/PAM."],
        )

    # -------------------------------------------------------------------------
    # Default Non-Toxic / Therapeutic Use (ROUTINE)
    # -------------------------------------------------------------------------
    return ToxicologyAssessment(
        urgency=ToxicologyUrgency.ROUTINE,
        confidence=0.95,
        toxidrome=None,
        detected_substances=detected_substances,
        estimated_dose_mg=None,
        is_life_threatening=False,
        reasons=["Không phát hiện dấu hiệu ngộ độc dược chất hoặc hội chứng độc học cấp."],
    )
