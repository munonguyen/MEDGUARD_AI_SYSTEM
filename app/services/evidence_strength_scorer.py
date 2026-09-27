"""Evidence Strength Scorer for MedGuard AI Candidate V9 (Workstream B).

Evaluates isolated single-symptom presentations (Singletons) using an evidence
strength hierarchy to prevent both under-triage of high-information loss-of-function
emergencies and over-triage of non-specific complaints.

Hierarchy:
1. CRITICAL_SINGLETON -> Mandatory EMERGENCY floor.
2. STRONG_SINGLETON   -> EMERGENCY with supporting context; else URGENT provisional floor.
3. WEAK_SINGLETON     -> No auto escalation (Preserves Specificity >= 95%).
4. AMBIGUOUS_SINGLETON-> Targeted clarification / routine triage pending verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any

from app.services.clinical_text import normalize_search_text


class SingletonEvidenceTier(str, Enum):
    CRITICAL_SINGLETON = "CRITICAL_SINGLETON"
    STRONG_SINGLETON = "STRONG_SINGLETON"
    WEAK_SINGLETON = "WEAK_SINGLETON"
    AMBIGUOUS_SINGLETON = "AMBIGUOUS_SINGLETON"


@dataclass(frozen=True)
class EvidenceStrengthAssessment:
    tier: SingletonEvidenceTier
    concept: str
    confidence: float
    recommended_floor: str  # "EMERGENCY" | "URGENT" | "ROUTINE"
    requires_targeted_clarification: bool
    rationale: str
    evidence_span: str = ""


# Catalog of high-information clinical singleton patterns
_CRITICAL_SINGLETON_PATTERNS: list[dict[str, Any]] = [
    {
        "concept": "acute_unilateral_blindness",
        "patterns": [
            r"\b(dot nhien khong nhin thay mot mat|mat thi luc mot mat|mu dot ngot mot ben|dot ngot khong thay gi o 1 mat|mat mot ben toi thui)\b",
            r"(?:dot nhien|tu nhien|bong nhien)\b.*?\b(?:khong nhin thay|chang thay gi)\b.*?\b(?:o mot mat|mot ben mat|1 mat)\b",
            r"\b(?:mot ben mat|mat mot ben|1 mat|mot mat|thi luc mot ben)\b.*?\b(?:toi thui|toi sam|mu|khong thay gi|khong nhin thay|chang thay gi)\b",
        ],
        "rationale": "Mất thị lực một mắt đột ngột là dấu hiệu cấp cứu tối khẩn (nghi tắc động mạch võng mạc trung tâm CRAO hoặc bong võng mạc cấp).",
    },
    {
        "concept": "acute_focal_limb_weakness",
        "patterns": [
            r"\b(?:tay|chan|nua nguoi|canh tay|chi)\b.*?\b(?:yeu|liet|roi do|khong gio|khong cam|khong di|khuyu|ru xuong|yeu xiu|rot cai dop|k cam dc)\b",
            r"\b(dot ngot khong gio duoc tay|tay cam coc nuoc thay yeu|yeu liet mot ben tay|chan tay nhu muon cua ai|dot nhien khong di lai duoc|khuyu chan dot ngot)\b",
        ],
        "rationale": "Yếu liệt chi hoặc mất vận động đột ngột là dấu hiệu tổn thương thần kinh khu trú cấp (nghi đột quỵ nhồi máu não).",
    },
    {
        "concept": "acute_facial_droop_speech",
        "patterns": [
            r"\b(?:mieng|mat|khoe mieng|moi|cai mieng)\b.*?\b(?:meo|lech|te ran|chay nuoc bot|chay nuoc dai|xe xuong|chay dai|lech queo|meo xeo)\b",
            r"\b(?:noi|tieng noi|phat am)\b.*?\b(?:ngong|u o|cung luoi|kho nghe|khong duoc)\b",
            r"\b(meo mieng dot ngot|lech mat dot ngot|te ran khoe mieng va nuoc bot chay|chay nuoc dai mot ben|u o khong noi thanh tieng|dot ngot khong noi duoc|noi ngong dot ngot|cung luoi|u o|noi ngong)\b",
        ],
        "rationale": "Méo miệng, chảy nước dãi một bên hoặc thất ngôn đột ngột là dấu hiệu đột quỵ cấp tối khẩn.",
    },
    {
        "concept": "acute_stridor_airway_collapse",
        "patterns": [
            r"\b(tho rit thanh quan|sung phu moi luoi khong tho duoc|nghet tho co keo|tieng tho rit ron nguoi|nuot nghen khong tho duoc)\b",
        ],
        "rationale": "Thở rít thanh quan hoặc phù mạch vùng hầu họng đe dọa tắc nghẽn đường thở hoàn toàn.",
    },
    {
        "concept": "bulging_fontanelle_infant",
        "patterns": [
            r"\b(thop phong|thop be phong len|thop cang phong|tre bu kem thop phong)\b",
            r"\bthop\b.*?\b(?:phong|cang phong|phong len)\b",
        ],
        "rationale": "Thóp phồng ở trẻ nhũ nhi là dấu hiệu tăng áp lực nội sọ cấp tính (nghi viêm màng não mủ).",
    },
    {
        "concept": "acute_limb_ischemia_sign",
        "patterns": [
            r"\b(?:chan|tay|chi|cang chan|ban chan|cai gio)\b.*?\b(?:lanh buot|lanh ngat|lanh gia|lanh cong|cold)\b.*?\b(?:trang bech|tai nhat|tai met|mat mach|khong bat duoc mach|absent pulse|no cho)\b",
            r"\b(chan lanh buot trang bech|chan mat mach hoan toan|tay lanh ngat khong bat duoc mach)\b",
        ],
        "rationale": "Tắc mạch chi cấp đe dọa hoại tử mô và mất chi nếu không tái tưới máu khẩn cấp.",
    },
]

_STRONG_SINGLETON_PATTERNS: list[dict[str, Any]] = [
    {
        "concept": "thunderclap_headache",
        "patterns": [
            r"\b(dau dau set danh|dau dau du doi chua tung co|dau dau nhu bua bo dot ngot)\b",
        ],
        "rationale": "Đau đầu sét đánh khởi phát cực điểm trong vài giây nghi ngờ xuất huyết dưới nhện.",
    },
    {
        "concept": "tearing_chest_pain",
        "patterns": [
            r"\b(dau nguc nhu xe|dau xe nguc lan ra sau lung|dau nguc du doi dot ngot)\b",
        ],
        "rationale": "Đau ngực dữ dội kiểu xé lan sau lưng nghi phình bóc tách động mạch chủ ngực.",
    },
    {
        "concept": "exertional_syncope",
        "patterns": [
            r"\b(ngat khi dang chay bo|ngat khi gang suc|dang tap the duc thi bat tinh)\b",
        ],
        "rationale": "Ngất khi gắng sức có nguy cơ loạn nhịp thất ác tính hoặc hẹp van động mạch chủ nặng.",
    },
    {
        "concept": "lumbar_radiculopathy",
        "patterns": [
            r"\b(?:dau (?:that )?lung|that lung|cot song)\b.*?\b(?:lan (?:xuong )?(?:mong|chan|dui|cang chan|ban chan)|kem te|te bi|te chan)\b",
            r"\b(?:lan (?:xuong )?(?:mong|chan|dui|cang chan|ban chan)|te bi chan)\b.*?\b(?:dau (?:that )?lung|that lung|cot song)\b",
            r"\b(?:lan xuong mong va chan|lan xuong mong|lan xuong chan|dau doc xuong chan)\b",
        ],
        "rationale": "Đau thắt lưng lan xuống mông hoặc chân kèm tê bì nghi ngờ kích thích hoặc chèn ép rễ thần kinh thắt lưng cần được đánh giá y tế sớm.",
    },
]

_AMBIGUOUS_SINGLETON_PATTERNS: list[dict[str, Any]] = [
    {
        "concept": "micturition_syncope",
        "patterns": [
            r"(?:di tieu|tieu tien|di ve sinh)\b.*?\b(?:ngat|xiu|ngat xiu)",
            r"(?:ngat|xiu|ngat xiu)\b.*?\b(?:khi di tieu|sau khi di tieu|sau khi tieu tien)",
        ],
        "rationale": "Ngất khi đi tiểu thường do phản xạ cường phế vị lành tính, cần sàng lọc thêm triệu chứng tim mạch.",
    },
    {
        "concept": "isolated_palpitations",
        "patterns": [
            r"\b(hoi hop danh trong nguc|tim dap nhanh thoang qua|thay tim hoi dap thinh thich)\b",
        ],
        "rationale": "Hồi hộp đánh trống ngực đơn độc có thể do lo âu, caffein hoặc rối loạn nhịp.",
    },
]

_WEAK_SINGLETON_PATTERNS: list[dict[str, Any]] = [
    {
        "concept": "isolated_sweating",
        "patterns": [
            r"\b(ra mo hoi nhe|hoi do mo hoi|mo hoi trom ve dem|hoi nong buc ra mo hoi)\b",
        ],
        "rationale": "Vã mồ hôi nhẹ đơn độc không đi kèm đau ngực hay trụy mạch.",
    },
    {
        "concept": "isolated_nausea",
        "patterns": [
            r"\b(buon non nhe|hoi non nao|thay nhe nhe da day|hoi day bung buon non)\b",
        ],
        "rationale": "Buồn nôn đơn độc không kèm nôn vọt, đau bụng cấp hay mất nước.",
    },
    {
        "concept": "isolated_fatigue",
        "patterns": [
            r"\b(met moi sau khi lam viec|nguoi thay ue oai|thay met met trong nguoi)\b",
        ],
        "rationale": "Mệt mỏi sinh lý sau làm việc, không có triệu chứng báo động đỏ.",
    },
]


# Benign mimics & physiological context exclusions for critical singletons
_BENIGN_CONTEXT_EXCLUSIONS: list[dict[str, Any]] = [
    {
        "target_concept": "acute_facial_droop_speech",
        "patterns": [
            r"\b(nha khoa|nho rang|tiem te|thuoc te|tram rang|boc rang)\b",
            r"(?:sau khi|vua)\s+(?:nho rang|tiem te|di nha khoa)",
        ],
        "rationale": "Méo miệng hoặc tê rần khoé miệng tạm thời do tác dụng của thuốc tê sau can thiệp nha khoa.",
    },
    {
        "target_concept": "acute_focal_limb_weakness",
        "patterns": [
            r"\b(?:tap ta|hit dat|gym|workout|chay bo|bong da|tap the duc|moi co sau tap|be vac|don dep|lao dong|khuan vac|mang vac|lam viec nang)\b",
            r"(?:sau khi|vua|hom qua|sau mot ngay)\s+(?:tap ta|tap luyen|hit dat|nang ta|tap the duc|don dep|be vac|lao dong|lam viec)",
        ],
        "rationale": "Mỏi cơ hoặc yếu mỏi tạm thời sau vận động thể lực nặng/tập tạ/lao động (DOMS), không phải tổn thương thần kinh cấp.",
    },
    {
        "target_concept": "acute_unilateral_blindness",
        "patterns": [
            r"\b(?:kinh ban|bui bay vao|nhin man hinh|moi mat|chua lau kinh|duc thuy tinh the lau nam|nhieu nam nay|nhieu thang nay)\b",
            r"(?:do|vi)\s+(?:kinh ban|bui|nhin may tinh|moi mat)",
        ],
        "rationale": "Mắt mờ do mỏi mắt điều tiết, kính bẩn, bụi hoặc bệnh lý mạn tính, không phải tắc mạch võng mạc cấp.",
    },
    {
        "target_concept": "acute_limb_ischemia_sign",
        "patterns": [
            r"\b(?:ngoi phong dieu hoa|may lanh|troi lanh|quen di tat|di mua|thoi tiet lanh)\b",
            r"(?:do|vi|ngoi)\s+(?:dieu hoa|may lanh|troi lanh)",
        ],
        "rationale": "Chi lạnh do phản xạ co mạch sinh lý khi tiếp xúc môi trường lạnh/điều hòa, không có tắc mạch cấp.",
    },
]


def _is_negated_match(norm_text: str, match_start: int) -> bool:
    """Check if a symptom match is preceded by explicit negation in the same clause."""
    preceding = norm_text[max(0, match_start - 45):match_start]
    clauses = re.split(r"[,.;]|\b(?:nhung|tuy nhien|ma)\b", preceding)
    clause_before = clauses[-1].strip()
    negation_patterns = (
        r"\b(?:khong phai|khong he|khong co|khong bi|chua tung|khong bao gio|nhin nham|loai tru|khong con|het bi|khong he bi|khong phai bi|chua he|chua bi|khong)\b"
    )
    if re.search(negation_patterns, clause_before):
        if re.search(r"\bkhong ro\b", clause_before) and not re.search(r"\b(?:khong phai|khong he|khong co|khong bi|chua|nhin nham|khong)\b(?!\s*ro\b)", clause_before):
            return False
        return True
    return False


def score_evidence_strength(text: str, has_supporting_context: bool = False) -> EvidenceStrengthAssessment:
    """Assess whether an isolated finding constitutes a Critical, Strong, Weak, or Ambiguous Singleton."""
    norm = normalize_search_text(text)

    # 1. Check Critical Singletons
    for item in _CRITICAL_SINGLETON_PATTERNS:
        concept = item["concept"]
        for pat in item["patterns"]:
            m = re.search(pat, norm)
            if m:
                if _is_negated_match(norm, m.start()):
                    continue
                # Check if this symptom is explained by a clear benign context
                is_benign_mimic = False
                benign_rationale = ""
                for excl in _BENIGN_CONTEXT_EXCLUSIONS:
                    if excl["target_concept"] == concept:
                        for excl_pat in excl["patterns"]:
                            if re.search(excl_pat, norm):
                                is_benign_mimic = True
                                benign_rationale = excl["rationale"]
                                break
                    if is_benign_mimic:
                        break

                if is_benign_mimic:
                    return EvidenceStrengthAssessment(
                        tier=SingletonEvidenceTier.WEAK_SINGLETON,
                        concept=f"benign_{concept}",
                        confidence=0.92,
                        recommended_floor="ROUTINE",
                        requires_targeted_clarification=False,
                        rationale=benign_rationale,
                        evidence_span=m.group(0),
                    )

                # Special disambiguation: Leg weakness in context of back pain / radiculopathy vs Stroke
                if concept == "acute_focal_limb_weakness":
                    is_spinal_radicular = bool(re.search(
                        r"\b(dau lung|that lung|cot song|dau doc|thoat vi|than kinh toa|kho nhac chan|te chan|te bi|kho buoc|ngoi lau|ngoi may tinh|kho nhac|kem te)\b",
                        norm,
                    ))
                    has_stroke_specific = bool(re.search(
                        r"\b(meo mieng|meo mat|noi ngong|u o|mat ngon ngu|nua nguoi|liet nua nguoi|te nua nguoi|canh tay|rot dua|rot coc)\b",
                        norm,
                    ))
                    if is_spinal_radicular and not has_stroke_specific:
                        has_cauda_equina = bool(re.search(
                            r"\b(bi tieu|tieu khong tu chu|dai tien khong tu chu|te yen ngua|te hau mon|yeu ca hai chan|liet ca hai chan|yeu tang nhanh)\b",
                            norm,
                        ))
                        if has_cauda_equina:
                            return EvidenceStrengthAssessment(
                                tier=SingletonEvidenceTier.CRITICAL_SINGLETON,
                                concept="acute_cauda_equina_syndrome",
                                confidence=0.98,
                                recommended_floor="EMERGENCY",
                                requires_targeted_clarification=False,
                                rationale="Dấu hiệu chèn ép chùm đuôi ngựa hoặc tủy sống cấp tính (yếu chân tiến triển nhanh kèm bí tiểu hoặc rối loạn cơ tròn).",
                                evidence_span=m.group(0),
                            )
                        else:
                            return EvidenceStrengthAssessment(
                                tier=SingletonEvidenceTier.STRONG_SINGLETON,
                                concept="lumbar_radicular_motor_involvement",
                                confidence=0.95,
                                recommended_floor="URGENT",
                                requires_targeted_clarification=False,
                                rationale="Triệu chứng yếu chân hoặc khó nhấc chân mới xuất hiện trong bối cảnh đau thắt lưng lan chân và tê bì nghi ngờ tổn thương rễ thần kinh thắt lưng cần được đánh giá y tế trong ngày.",
                                evidence_span=m.group(0),
                            )

                return EvidenceStrengthAssessment(
                    tier=SingletonEvidenceTier.CRITICAL_SINGLETON,
                    concept=item["concept"],
                    confidence=0.99,
                    recommended_floor="EMERGENCY",
                    requires_targeted_clarification=False,
                    rationale=item["rationale"],
                    evidence_span=m.group(0),
                )

    # 2. Check Strong Singletons
    for item in _STRONG_SINGLETON_PATTERNS:
        for pat in item["patterns"]:
            m = re.search(pat, norm)
            if m:
                if _is_negated_match(norm, m.start()):
                    continue
                floor = "EMERGENCY" if has_supporting_context else "URGENT"
                return EvidenceStrengthAssessment(
                    tier=SingletonEvidenceTier.STRONG_SINGLETON,
                    concept=item["concept"],
                    confidence=0.95,
                    recommended_floor=floor,
                    requires_targeted_clarification=not has_supporting_context,
                    rationale=item["rationale"],
                    evidence_span=m.group(0),
                )

    # 3. Check Ambiguous Singletons
    for item in _AMBIGUOUS_SINGLETON_PATTERNS:
        for pat in item["patterns"]:
            m = re.search(pat, norm)
            if m:
                if _is_negated_match(norm, m.start()):
                    continue
                return EvidenceStrengthAssessment(
                    tier=SingletonEvidenceTier.AMBIGUOUS_SINGLETON,
                    concept=item["concept"],
                    confidence=0.90,
                    recommended_floor="ROUTINE",
                    requires_targeted_clarification=True,
                    rationale=item["rationale"],
                    evidence_span=m.group(0),
                )

    # 4. Check Weak Singletons
    for item in _WEAK_SINGLETON_PATTERNS:
        for pat in item["patterns"]:
            m = re.search(pat, norm)
            if m:
                if _is_negated_match(norm, m.start()):
                    continue
                return EvidenceStrengthAssessment(
                    tier=SingletonEvidenceTier.WEAK_SINGLETON,
                    concept=item["concept"],
                    confidence=0.92,
                    recommended_floor="ROUTINE",
                    requires_targeted_clarification=False,
                    rationale=item["rationale"],
                    evidence_span=m.group(0),
                )

    # Default if no specific singleton recognized
    return EvidenceStrengthAssessment(
        tier=SingletonEvidenceTier.WEAK_SINGLETON,
        concept="unspecified_isolated_complaint",
        confidence=0.85,
        recommended_floor="ROUTINE",
        requires_targeted_clarification=False,
        rationale="Không phát hiện triệu chứng cô lập có giá trị thông tin khẩn cấp.",
    )
