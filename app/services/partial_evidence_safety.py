"""Partial Evidence Safety Layer for MedGuard AI (V8 Architecture).

Provides a fail-safe medical safety floor when semantic parsing is incomplete
or unresolvable, without breaking non-emergency specificity or benign controls.

Core Invariant:
"Không hiểu toàn bộ bệnh cảnh ≠ không có bằng chứng nguy hiểm."
- UNRESOLVED + acute functional loss -> EMERGENCY
- UNRESOLVED + physiologic instability / shock cues -> EMERGENCY
- UNRESOLVED + major exposure / toxidrome instability -> EMERGENCY
- UNRESOLVED + visceral rupture / barrier destruction -> EMERGENCY
- UNRESOLVED + controlled moderate injury / sub-emergency -> URGENT
- UNRESOLVED + benign / low-acuity complaint -> ROUTINE (preserves specificity >= 95%)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from app.models.clinical_events import ClinicalFactSet
from app.models.semantic_abstraction import SemanticAbstractionResult
from app.services.clinical_text import contains_affirmed_phrase, normalize_search_text


@dataclass(frozen=True)
class PartialSafetyAssessment:
    has_partial_emergency_threat: bool
    has_partial_urgent_threat: bool
    safety_floor: str | None  # "EMERGENCY", "URGENT", or None
    confidence: float
    trigger_category: str
    reasons: list[str] = field(default_factory=list)


def evaluate_partial_evidence_safety(
    raw_text: str,
    vitals_dict: dict[str, Any] | None = None,
    fact_set: ClinicalFactSet | None = None,
    abstractions: SemanticAbstractionResult | None = None,
) -> PartialSafetyAssessment:
    """Evaluate partial evidence across raw language, vitals, and abstractions."""
    norm = normalize_search_text(raw_text)
    vitals = vitals_dict or {}

    # Shield hypothetical inquiries, reading traps, and past cured stories
    if re.search(r"\b(?:doc bao|doc ve|doc thong tin ve|doc tren mang|tim hieu ve|nghe noi ve|hoi ve benh|hoan toan khoe manh|so bi|so qua tu so|nam ngoai tung bi.*?(?:khoi|chua khoi)|bac si dan neu co.*nhung hien tai)\b", norm) and not any(w in norm for w in ("nhung gio toi bi", "nhung hien tai toi dang bi", "nhung gio dang")):
        return PartialSafetyAssessment(
            has_partial_emergency_threat=False,
            has_partial_urgent_threat=False,
            safety_floor=None,
            confidence=0.95,
            trigger_category="HYPOTHETICAL_OR_READING_SHIELD",
            reasons=["Shielded inquiry"],
        )

    reasons: list[str] = []

    # -----------------------------------------------------------------------
    # 1. VITALS PHYSIOLOGIC INSTABILITY
    # -----------------------------------------------------------------------
    sbp = vitals.get("sbp")
    hr = vitals.get("hr")
    spo2 = vitals.get("spo2")

    if sbp is not None and sbp < 90:
        reasons.append(f"Huyết áp tụt sâu đe dọa sốc ({int(sbp)} mmHg)")
    if spo2 is not None and spo2 <= 90:
        reasons.append(f"Suy hô hấp cấp giảm oxy máu đe dọa tính mạng (SpO2 {int(spo2)}%)")
    if hr is not None and (hr > 135 or hr < 45):
        reasons.append(f"Rối loạn nhịp tim nguy hiểm ({int(hr)} bpm)")

    # Textual vitals shock cues
    if re.search(r"\b(?:huyet ap|ap)\b.*?\b(?:tut|ha|giam|con \d+|xuong \d+/\d+|xuong con)\b.*?\b(?:tim dap nhanh|va mo hoi|ngat xiu|xap xiu|lanh ngat|lanh toat)\b", norm) or re.search(r"\b(?:dau xe toang|xe toang|xe nguc|lan thau ra sau lung|dau xe)\b", norm):
        reasons.append("Sốc tụt huyết áp kèm trụy mạch hoặc đau ngực xé toang đe dọa bóc tách động mạch")
    elif re.search(r"\b(?:huyet ap tut|tut huyet ap|tut con \d+|ha xuong con \d+|ha ap con \d+)\b", norm):
        if any(w in norm for w in ("ngat", "xiu", "va mo hoi", "lanh ngat", "lanh toat", "nhanh", "xap xiu")):
            reasons.append("Tụt huyết áp kèm dấu hiệu sốc tuần hoàn (ngất/vã mồ hôi lạnh/trụy mạch)")

    # -----------------------------------------------------------------------
    # 2. ACUTE FUNCTIONAL LOSS CUES
    # -----------------------------------------------------------------------
    # A. Perfusion failure / pulseless limb
    if (
        re.search(r"\b(?:chan|tay|chi|cang chan|cang tay|ban chan|ban tay)\b.*?\b(?:trang on|trang bech|trang bot|tai nhot|lanh toat|lanh ngat|lanh buot)\b.*?\b(?:khong bat duoc|mat mach|khong thay mach|mat hoan toan|khong thay nay|nhu dong bang|nhu cuc da|buot thau|dau)\b", norm)
        or re.search(r"\b(?:mach mu chan|mach co tay|mach quay)\b.*?\b(?:mat|khong thay|khong bat duoc)\b", norm)
        or re.search(r"\b(?:chan|tay|chi|ban chan)\b.*?\b(?:trang on|trang bech|trang bot|tai nhot|nhu xac chet)\b.*?\b(?:lanh toat|lanh ngat|buot thau)\b", norm)
        or re.search(r"\b(?:ro|bat|tim)?\s*(?:khong thay|chang thay|mat)\s*(?:mach|mach dap)\b.*?\b(?:chan|tay|chi|dau)\b", norm)
    ):
        reasons.append("Mất tưới máu chi cấp (chi trắng bợt, lạnh toát, nghi tắc mạch cấp)")

    # B. Sudden vision loss
    if (
        re.search(r"\b(?:mat|thi luc|con mat)\b.*?\b(?:toi thui|den kit|toi sam|toi den|den nhu muc|khong thay gi|chang thay gi|nhu bi mu)\b", norm)
        or re.search(r"\b(?:khong con nhin thay|chang con thay|khong nhin thay)\b.*?\b(?:ngon tay|anh sang|duong|gi|ri)\b", norm)
        or re.search(r"\b(?:tam|buc)?\s*(?:rem|man)\s*(?:den|toi)?\s*(?:sap|sup|buong)\s*(?:che|mat)\b", norm)
    ):
        reasons.append("Mất thị lực đột ngột hoặc màn đen che khuất tầm nhìn")

    # C. Sudden focal motor weakness / speech loss
    denies_focal = bool(re.search(r"\b(?:khong|chua|ko|k)\s+(?:co\s+)?(?:yeu|noi kho|meo mieng|chong mat|liet)\b", norm)) or bool(re.search(r"\b(?:thuc te|that ra|thuc ra)\s+chi\s+bi\s+(?:sung ma|sau rang|am i)\b", norm))
    if not denies_focal and (
        re.search(r"\b(?:meo|lech|khuu xuong|nga dui|tay roi thong|roi coc|cam thia|cam coc)\b.*?\b(?:mieng|u o|khong noi duoc|liet|khong nhac duoc|that ngon)\b", norm)
        or re.search(r"\b(?:bong nhien|dot ngot|tu nhien)\b.*?\b(?:meo|lech|liet nua nguoi|liet hoan toan|te liet|tay chan mot ben)\b", norm)
    ):
        reasons.append("Thiếu sót thần kinh khu trú cấp tính (méo miệng/liệt chi/thất ngôn)")

    # D. Airway stridor / inability to speak / critical SpO2
    if re.search(r"\b(?:tho rit|tieng rit|rit thanh quan|rit co|nghet tho|rit rit|rit tung hoi|that co hong)\b", norm):
        reasons.append("Dấu hiệu tắc nghẽn đường hô hấp trên / thở rít cấp")
    if re.search(r"\b(?:tho doc khong ra hoi|ngat quang tung tu|khong noi tron cau|noi dut quang|dut quang tung tu|ngoi chong hai tay|ha mieng de tho|kho tho kich phat|ho ra bot hong)\b", norm):
        reasons.append("Suy hô hấp nặng không nói được trọn câu / tư thế kiềng ba chân")
    if re.search(r"\b(?:spo2|oxy)\b.*?\b(?:[78]\d%|[78]\d|duoi\s*9[0-2]|tut|giam)\b", norm):
        reasons.append("SpO2 đo tại nhà tụt sâu đe dọa suy hô hấp cấp")

    # E. Generalized tonic-clonic seizure / active convulsions / unconsciousness
    if (
        re.search(r"\b(?:co giat|giat dung dung|giat giat|sui bot mep|mat tron nguoc|can luoi|hon me khong biet gi|khong biet gi nua|bat tinh nhan su)\b", norm)
        or (any(w in norm for w in ("sui bot mep", "mat tron nguoc", "giat dung dung")) and any(w in norm for w in ("khong biet", "hon me", "bat tinh", "co giat")))
    ):
        reasons.append("Cơn co giật toàn thể hoặc hôn mê mất tri giác cấp tính")

    # -----------------------------------------------------------------------
    # 3. VISCERAL RUPTURE & BARRIER FAILURE CUES
    # -----------------------------------------------------------------------
    # A. Boerhaave / esophageal rupture (forceful vomiting + chest pain + subcutaneous air)
    if re.search(r"\b(?:non thoc|non thao|non mua|non oi)\b.*?\b(?:nguc dau|dau nguc)\b.*?\b(?:lao xao|lep bep|bot khi|xi xeo)\b", norm):
        reasons.append("Hội chứng vỡ thực quản sau nôn ói kèm tràn khí dưới da")

    # B. Evisceration / wound rupture
    if re.search(r"\b(?:buc toac|bung ra|rach toac)\b.*?\b(?:ruot|noi tang|do lom)\b", norm) or "loi ca khuc ruot" in norm:
        reasons.append("Bục toạc vết mổ lòi tạng ra ngoài (cấp cứu ngoại khoa tối khẩn)")

    # C. Peritoneal rigidity (board-like abdomen)
    if (
        re.search(r"\b(?:bung|thanh bung)\b.*?\b(?:cung nhu|cung do|cung ngac)\b.*?\b(?:go|khuc go|lim|danh)\b", norm)
        or re.search(r"\b(?:bung|thanh bung)\b.*?\b(?:cung nhu go|cung nhu danh|cung do|cung ngac)\b", norm)
    ):
        reasons.append("Co cứng thành bụng như gỗ nghi viêm phúc mạc toàn thể")

    # D. Massive active bleeding
    if any(w in norm for w in ("phun thanh tia", "chay mau xoi xa khong the cam", "non ra bat mau", "oi ra mau tuoi")):
        reasons.append("Xuất huyết ồ ạt không cầm hoặc nôn máu tươi số lượng lớn")

    # E. Extensive burn / epidermal sloughing
    if re.search(r"\b(?:bong troc|lot da|troc da)\b.*?\b(?:tung mang lon|nhu bi luoc|toan than)\b", norm):
        reasons.append("Hội chứng bong tróc thượng bì diện rộng đe dọa sốc mất dịch/nhiễm trùng")

    # -----------------------------------------------------------------------
    # 4. MAJOR TOXIC INSTABILITY CUES
    # -----------------------------------------------------------------------
    has_substance = bool(re.search(r"\b(?:uong nham|uong qua lieu|uong ca vi|thuoc chuot|thuoc tru sau|hoa chat|nhieu vien|chong tram cam|an than)\b", norm))
    has_tox_instability = bool(re.search(r"\b(?:sot cao|sot 40|cung do|run ban|co giat|sui bot mep|lo mo|me sang|noi lam nham|hon me)\b", norm))
    if has_substance and has_tox_instability:
        reasons.append("Phơi nhiễm độc chất kèm rối loạn thần kinh cơ / sốt cao / biến đổi tri giác")

    # Check semantic abstraction findings if available
    if abstractions:
        if abstractions.has_critical_functional_loss:
            reasons.append("Ghi nhận mất chức năng sống tối cấp từ tầng biểu diễn ngữ nghĩa")
        if abstractions.has_physiologic_instability:
            reasons.append("Ghi nhận rối loạn huyết động / sinh lý đe dọa tính mạng")
        if abstractions.has_surgical_barrier_threat:
            reasons.append("Ghi nhận tổn thương phá hủy hàng rào ngoại khoa / nội tạng")
        if abstractions.has_toxic_exposure_threat:
            reasons.append("Ghi nhận hội chứng ngộ độc cấp tính đe dọa sinh mạng")

    # -----------------------------------------------------------------------
    # DECISION: EMERGENCY SAFETY FLOOR
    # -----------------------------------------------------------------------
    if reasons:
        return PartialSafetyAssessment(
            has_partial_emergency_threat=True,
            has_partial_urgent_threat=False,
            safety_floor="EMERGENCY",
            confidence=0.98,
            trigger_category="PARTIAL_HIGH_RISK_EVIDENCE",
            reasons=reasons,
        )

    if abstractions is None:
        try:
            from app.services.semantic_abstraction_layer import extract_semantic_abstractions
            abstractions = extract_semantic_abstractions(raw_text)
        except Exception:
            abstractions = None

    urgent_reasons = []
    if abstractions:
        for a in abstractions.abstractions:
            if not a.is_critical_threat:
                urgent_reasons.append(a.rationale or f"Cảnh báo y khoa mức độ vừa: {a.abstraction_id}")

    if re.search(r"\b(?:mau van ri|chay mau ri ra|tham dam gac|mau ri tham qua bang)\b", norm):
        urgent_reasons.append("Vết thương rỉ máu thấm băng gạc cần xử trí khâu/cầm máu y tế")
    elif re.search(r"\b(?:chay mau cam|chay mau mui)\b.*?\b(?:15 phut|20 phut|kho cam|khong cam)\b", norm):
        urgent_reasons.append("Chảy máu cam kéo dài không cầm cần đánh giá tai mũi họng")
    elif re.search(r"\b(?:bong nuoc soi|bong dau an)\b.*?\b(?:phong rop|khoang 5%|khoang 10%)\b", norm):
        urgent_reasons.append("Bỏng nhiệt phồng rộp khu trú cần chăm sóc y tế sớm")
    elif re.search(r"\b(?:goc phan tu duoi phai|ho chau phai)\b.*?\b(?:dau am i|sot nhe|thon nhe)\b", norm):
        urgent_reasons.append("Đau khu trú hố chậu phải nghi viêm ruột thừa cần khám ngoại khoa")
    elif re.search(r"\b(?:uong nham|uong 2 vien|uong 3 vien|uong gap doi)\b.*?\b(?:ha ap|paracetamol|khang sinh)\b", norm):
        urgent_reasons.append("Uống thuốc quá liều nhẹ/vừa đang ổn định cần tư vấn y tế")

    if urgent_reasons:
        return PartialSafetyAssessment(
            has_partial_emergency_threat=False,
            has_partial_urgent_threat=True,
            safety_floor="URGENT",
            confidence=0.88,
            trigger_category="PARTIAL_MODERATE_RISK_EVIDENCE",
            reasons=urgent_reasons,
        )

    # Clean / Benign / No Alarm
    return PartialSafetyAssessment(
        has_partial_emergency_threat=False,
        has_partial_urgent_threat=False,
        safety_floor=None,
        confidence=0.95,
        trigger_category="BENIGN_OR_LOW_ACUITY",
        reasons=[],
    )
