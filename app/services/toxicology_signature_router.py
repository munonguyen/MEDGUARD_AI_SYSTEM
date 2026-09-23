"""Toxicity Signature Router for MedGuard AI Candidate V9 (Workstream C).

Routes suspected toxicological exposures based on clinical 'Toxicity Signatures'
(Exposure event + Systemic disturbance + Autonomic/Neuro/Cardio/GI findings)
rather than rigid chemical keyword dictionaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Sequence

from app.services.clinical_text import normalize_search_text
from app.services.clinical_text import contains_affirmed_phrase


class ToxicityDimension(str, Enum):
    EXPOSURE_EVENT = "exposure_event"
    ACUTE_TIMING = "acute_timing"
    AUTONOMIC_SIGNS = "autonomic_signs"
    CARDIOVASCULAR_SIGNS = "cardiovascular_signs"
    NEUROLOGIC_SIGNS = "neurologic_signs"
    GI_DISTURBANCE = "gi_disturbance"
    RESPIRATORY_METABOLIC = "respiratory_metabolic"


@dataclass(frozen=True)
class ToxicitySignatureResult:
    is_toxicology_eligible: bool
    is_emergency_toxidrome: bool
    matched_dimensions: list[ToxicityDimension]
    confidence: float
    suspected_syndrome: str
    rationale: str
    immediate_interventions: list[str] = field(default_factory=list)


# Dimension detection rules
_DIMENSION_PATTERNS: dict[ToxicityDimension, list[str]] = {
    ToxicityDimension.EXPOSURE_EVENT: [
        r"\b(?:uong|nuot|an)\b.*?\b(?:nham|qua lieu|ca vi|ca lo|nhieu vien|phai|\d+\s+vien|tu hai|tu tu)\b",
        r"\b(?:uong|nuot|an)\b.*?\b(?:nhieu vien|lo thuoc|vien thuoc|chat tay|hoa chat)\b",
        r"\b(?:thuoc\s+(?:tru\s+)?sau|thuoc\s+(?:diet\s+)?chuot|thuoc\s+bao\s+ve\s+thuc\s+vat|thuoc\s+diet\s+oc|thuoc\s+diet\s+co|paraquat)\b",
        r"\b(?:nam|lau nam)\b.*?\b(?:hai|tren rung|rung|doc|la|trang|hoang)\b",
        r"\b(ngo doc nam|an lau nam|nam hai tren rung|ruou ngam|ruou thuoc|cu au tau|la ngon|nam la|nam rung|nam doc|nam trang|re cay la|re cay|thuoc nam khong ro|thuoc gia truyen|bot la|ma tien|truc dao|thau dau|so bien|ca noc|ca doc duoc|thuoc bac ngam ruou)\b",
        r"\b(thuoc tay|nuoc tay rua|dau hoa|xang|hoa chat|chat tay rua|clo|javen|axit|xut|con cong nghiep|than hoa|suoi than|bep than)\b",
        r"(?:be|tre|con nho)\b.*?\b(?:choi canh|lo thuoc|ngam vien|nuot|nhat vien|ngam pin|uong nham)\b",
        r"\b(?:ong|ran|bo cap|kien ba khoang|sau rom|con trung)\b.*?\b(?:dot|can|chich)\b",
    ],
    ToxicityDimension.ACUTE_TIMING: [
        r"\b(?:sau|trong|duoc)?\s*\d+\s*(?:phut|tieng|gio)\b",
        r"\b(vua moi uong|ngay sau khi an|vua an xong|vua uong xong|uong vai phut)\b",
    ],
    ToxicityDimension.AUTONOMIC_SIGNS: [
        r"\b(dong tu co nho|dong tu gian|tang tiet dom dai|chay nuoc dai|chay nuoc mieng|va mo hoi|do mo hoi|mo hoi dam dia|do bung mat|kho mieng|mui toi|hoi tho hoi mui toi)\b",
    ],
    ToxicityDimension.CARDIOVASCULAR_SIGNS: [
        r"\b(tim dap cham|mach cham|loan nhip tim|tim dap thinh thich|tim dap nhanh|loan xa|loan nhip|tut huyet ap|ha huyet ap|choang vang ngat xiu)\b",
    ],
    ToxicityDimension.NEUROLOGIC_SIGNS: [
        r"\b(co giat|rung giat co|co cung|lo mo|me sang|hon me|goi khong biet|ao giac|te ran moi mieng|te dai dau luoi|kho nuot|sup mi mat|liet co ho hap|liet tu chi)\b",
    ],
    ToxicityDimension.GI_DISTURBANCE: [
        r"\b(non mua|non ra mau|non tro|bong rat mieng hong|rat bong mieng hong|bong rat|rat bong|bong rat thuc quan|dau bung quan|dau bung that|tieu chay|non thoc thao|non oi|buon non|di ngoai ra mau|da vang mat vang|vang da vang mat|vang mat vang da)\b",
    ],
    ToxicityDimension.RESPIRATORY_METABOLIC: [
        r"\b(tho cham|tho yeu|ngung tho|tho nhanh nong|tho sau kussmaul|tim tai moi|suy ho hap|dai ra nuoc tieu mau den|kho tho tho rit)\b",
    ],
}


# Therapeutic / Benign normal consumption patterns to exclude from toxic routing
_BENIGN_THERAPEUTIC_PATTERNS: list[str] = [
    r"\b(?:dung lieu|dung chi dinh|theo don|1 vien|mot vien|uong vien bo|vitamin|uong nuoc cam|uong sua)\b",
    r"\b(?:tra hoa cuc|tra atiso|tra thao moc thong thuong|tra gung|tra sen|tra xanh|nuoc che)\b",
    r"\b(?:khong co trieu chung|hoan toan binh thuong|khong thay gi bat thuong|suc khoe on dinh)\b",
]


def _detect_severe_syndromic_toxidrome(norm: str) -> tuple[bool, str, str]:
    """Detect complete severe physiological toxidromes without requiring explicit toxin name."""
    def affirmed(*phrases: str) -> bool:
        return any(contains_affirmed_phrase(norm, phrase) for phrase in phrases)

    # 1. Anticholinergic Toxidrome (Hot, Dry, Red, Blind, Mad)
    has_hyperthermia = affirmed("nong ran", "da do", "do bung", "sot cao", "nong nhu than")
    has_dry_skin = affirmed("kho queo", "da kho", "khong co mo hoi", "khong mot giot mo hoi", "khong tiet mo hoi", "kho mieng")
    # These findings often follow the defining phrase "không có mồ hôi" in
    # the same sentence.  Match their own clause so that the earlier negation
    # does not incorrectly scope across a comma and conjunction.
    has_mydriasis = bool(re.search(r"\b(?:dong tu gian|dong tu to|gian dong tu)\b", norm))
    has_delirium = bool(re.search(r"\b(?:lam nham|noi sang|me sang|kich dong|ao giac|noi loan|noi vo thuc)\b", norm))
    if has_hyperthermia and has_dry_skin and has_mydriasis and has_delirium:
        return (
            True,
            "severe_anticholinergic_toxidrome",
            "Hội chứng kháng Cholinergic rầm rộ cấp cứu (sốt cao/da đỏ khô không mồ hôi, đồng tử giãn to, kích động nói sảng); nguy cơ sốc nhiệt và suy đa tạng tối khẩn.",
        )

    # 2. Severe Sympathomimetic Toxidrome
    has_severe_tachycardia = bool(re.search(r"\b(tim dap loan|160|150|loan xa|loan nhip|nhip tim nhanh|mach 160|mach 150)\b", norm))
    has_diaphoresis = affirmed("va mo hoi", "mo hoi dam dia", "do mo hoi")
    has_severe_agitation = affirmed("run ban", "kich dong", "hung han", "hoang loan", "kich dong hung han")
    if has_severe_tachycardia and has_diaphoresis and has_mydriasis and has_severe_agitation:
        return (
            True,
            "severe_sympathomimetic_toxidrome",
            "Hội chứng cường giao cảm nặng (nhịp tim cực nhanh, vã mồ hôi đầm đìa, run bắn, kích động hung hãn, đồng tử giãn); nguy cơ nhồi máu cơ tim, đột quỵ và loạn nhịp tử vong.",
        )

    # 3. Marine Biological / Paralytic Neurotoxin
    has_marine_exposure = affirmed("hai san la", "so bien la", "ca noc", "bach tuoc la", "cua la")
    has_perioral_numbness = affirmed("te ran", "te moi", "te dau luoi", "te quanh moi", "te moi mieng")
    has_paralysis_dyspnea = affirmed("liet", "liet dan", "yeu liet", "hut hoi", "tho khong noi", "kho tho", "suy ho hap")
    if has_marine_exposure and has_perioral_numbness and has_paralysis_dyspnea:
        return (
            True,
            "marine_neurotoxin_paralytic_poisoning",
            "Ngộ độc độc tố sinh học biển cấp tính (nghi ngộ độc Tetrodotoxin/Saxitoxin sau ăn hải sản lạ kèm tê môi lưỡi và liệt cơ hô hấp tiến triển); nguy cơ ngừng thở tối khẩn.",
        )

    # 4. Caustic Airway Injury
    has_caustic_agent = bool(re.search(r"\b(?:nuot|uong)\b.*?\b(?:nuoc tay|clo|javen|axit|xut|chat tay|hoa chat)\b", norm))
    has_airway_stridor = bool(re.search(r"\b(thanh quan|phu ne|tho rit|rit len|tim tai|kho tho|nghet tho)\b", norm))
    if has_caustic_agent and has_airway_stridor:
        return (
            True,
            "caustic_airway_edema_emergency",
            "Nuốt phải hóa chất ăn mòn kèm phù nề thanh quản và thở rít cấp tính; nguy cơ tắc nghẽn đường thở hoàn toàn đe dọa tính mạng.",
        )

    # 5. Severe Cholinergic Toxidrome (SLUDGE / DUMBELS)
    has_salivation = bool(re.search(r"\b(chay nuoc dai|chay nuoc mieng|tang tiet dom dai|dom dai)\b", norm))
    has_miosis = bool(re.search(r"\b(dong tu co nho|co nho nhu dau kim|co nho)\b", norm))
    has_fasciculations = bool(re.search(r"\b(rung giat co|co giat|giat co)\b", norm))
    if has_salivation and has_miosis and (has_fasciculations or has_diaphoresis):
        return (
            True,
            "severe_cholinergic_toxidrome",
            "Hội chứng ngộ độc Cholinergic cấp rầm rộ (tăng tiết đờm dãi, đồng tử co nhỏ, rung giật cơ); nguy cơ suy hô hấp do co thắt phế quản tối khẩn.",
        )

    return False, "", ""


def route_by_toxicity_signature(text: str) -> ToxicitySignatureResult:
    """Analyze clinical text for multi-dimensional toxicological signature."""
    norm = normalize_search_text(text)
    matched_dims: list[ToxicityDimension] = []

    # Check benign therapeutic or routine dietary consumption
    is_benign_intake = any(re.search(pat, norm) for pat in _BENIGN_THERAPEUTIC_PATTERNS)
    has_overdose_flag = bool(re.search(r"\b(nham|qua lieu|ca vi|ca lo|nhieu vien|doc chat|uong thuoc sau|tu tu)\b", norm))

    for dim, patterns in _DIMENSION_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, norm):
                # If exposure pattern matched on generic 'vien thuoc' but it's benign therapeutic dose without overdose flag
                if dim == ToxicityDimension.EXPOSURE_EVENT and is_benign_intake and not has_overdose_flag:
                    continue
                matched_dims.append(dim)
                break

    has_exposure = ToxicityDimension.EXPOSURE_EVENT in matched_dims
    has_timing = ToxicityDimension.ACUTE_TIMING in matched_dims
    has_autonomic = ToxicityDimension.AUTONOMIC_SIGNS in matched_dims
    has_cardio = ToxicityDimension.CARDIOVASCULAR_SIGNS in matched_dims
    has_neuro = ToxicityDimension.NEUROLOGIC_SIGNS in matched_dims
    has_gi = ToxicityDimension.GI_DISTURBANCE in matched_dims
    has_resp = ToxicityDimension.RESPIRATORY_METABOLIC in matched_dims

    # Systemic disturbance exists if at least one vital/organ sign is triggered
    systemic_disturbances = [
        d for d in (has_autonomic, has_cardio, has_neuro, has_gi, has_resp) if d
    ]
    is_systemic = len(systemic_disturbances) >= 1
    is_lethal_substance = bool(re.search(
        r"\b(paraquat|thuoc diet chuot|thuoc sau|thuoc tru sau|la ngon|cu au tau|ma tien|tu tu|tu van|ran can|bo cap can)\b",
        norm,
    ))

    # Determination of Eligibility and Emergency
    is_eligible = False
    is_emergency = False
    suspected_syndrome = "unknown_toxic_exposure"
    rationale = "Không phát hiện yếu tố phơi nhiễm hay chữ ký độc học."
    interventions: list[str] = []

    # Priority 1: Check physiological severe toxidromes (independent of named toxin)
    is_syndromic_emergency, syn_name, syn_rationale = _detect_severe_syndromic_toxidrome(norm)
    if is_syndromic_emergency:
        is_eligible = True
        is_emergency = True
        suspected_syndrome = syn_name
        rationale = syn_rationale
        interventions = [
            "Đến ngay trung tâm chống độc hoặc khoa Cấp cứu 115 gần nhất.",
            "Mang theo mẫu đồ ăn, hóa chất hoặc thuốc nghi ngờ nếu có.",
            "Tuyệt đối không tự ý gây nôn; đặt người bệnh ở tư thế nghiêng an toàn nếu lơ mơ.",
        ]
    elif has_exposure and (is_systemic or is_lethal_substance):
        is_eligible = True
        is_emergency = True
        interventions = [
            "Đến ngay trung tâm chống độc hoặc khoa Cấp cứu 115 gần nhất.",
            "Mang theo mẫu nấm, lá cây, vỏ chai hoặc thuốc đã uống để bác sĩ định danh.",
            "Tuyệt đối không tự ý gây nôn nếu uống phải hóa chất ăn mòn hoặc bệnh nhân lơ mơ.",
        ]

        if is_lethal_substance and not is_systemic:
            suspected_syndrome = "lethal_toxin_or_suicidal_ingestion_emergency"
            rationale = "Phơi nhiễm độc chất kịch độc hoặc uống chất độc tự sát; nguy cơ suy đa tạng tử vong tối khẩn."
        elif has_autonomic and has_gi:
            suspected_syndrome = "cholinergic_or_organophosphate_toxidrome"
            rationale = "Phơi nhiễm độc chất kèm hội chứng Cholinergic (tăng tiết đờm dãi, vã mồ hôi, nôn tiêu chảy)."
        elif has_cardio and (has_neuro or has_gi):
            suspected_syndrome = "cardiotoxic_plant_or_alkaloid_poisoning"
            rationale = "Nghi ngộ độc cây cỏ/rượu ngâm chứa alkaloid ức chế tim mạch (như củ ấu tàu/aconitin) hoặc loạn nhịp cấp."
        elif has_neuro or has_resp:
            suspected_syndrome = "cns_and_respiratory_depression_toxicity"
            rationale = "Ngộ độc cấp đe dọa suy hô hấp hoặc ức chế thần kinh trung ương (co giật/hôn mê)."
        elif has_gi:
            suspected_syndrome = "acute_corrosive_or_gastrointestinal_toxidrome"
            rationale = "Ngộ độc cấp gây tổn thương niêm mạc tiêu hóa nặng (bỏng rát, nôn liên tục)."
        else:
            suspected_syndrome = "systemic_acute_poisoning"
            rationale = "Phơi nhiễm chất độc cấp tính có dấu hiệu rối loạn cơ quan hệ thống."

    elif has_exposure and has_timing and not (is_benign_intake and not has_overdose_flag):
        # Acute ingestion without severe symptoms yet -> still high urgency toxic routing
        is_eligible = True
        is_emergency = False
        suspected_syndrome = "acute_asymptomatic_or_early_exposure"
        rationale = "Ghi nhận phơi nhiễm chất lạ mới xảy ra; cần chuyển phân luồng độc chất để theo dõi trước khi độc tố ngấm vào máu."
        interventions = ["Theo dõi sát các dấu hiệu sinh tồn, không ăn uống thêm đồ lạ."]
    elif has_exposure and not (is_benign_intake and not has_overdose_flag):
        is_eligible = True
        is_emergency = False
        suspected_syndrome = "unspecified_exposure_risk"
        rationale = "Có yếu tố tiếp xúc độc chất hoặc uống nhầm thuốc; kích hoạt bộ suy luận độc chất học."

    return ToxicitySignatureResult(
        is_toxicology_eligible=is_eligible,
        is_emergency_toxidrome=is_emergency,
        matched_dimensions=matched_dims,
        confidence=0.98 if is_emergency else (0.90 if is_eligible else 0.60),
        suspected_syndrome=suspected_syndrome,
        rationale=rationale,
        immediate_interventions=interventions,
    )
