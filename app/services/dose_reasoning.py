"""Medication Dose Reasoning Engine for MedGuard AI.

Implements clinical pharmacokinetic and toxicological reasoning:
- Extracts drug, tablet count, tablet strength, total dose, patient weight, time window, and ingestion pattern.
- Performs weight-aware and time-aware risk stratification (e.g. APAP toxic thresholds in adults and children).
- Strictly separates Triage Risk Assessment & Disposition from Clinical Treatment Execution:
  Never prescribes invasive procedures (e.g. gastric lavage) or specific antidotes (e.g. NAC)
  as mandatory directives at the triage layer. Recommends prompt emergency/poison center evaluation,
  packaging retention, and serum level testing as determined by treating physicians.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from app.services.clinical_text import normalize_search_text


@dataclass(frozen=True)
class DoseAssessment:
    drug: str
    tablet_strength_mg: float | None = None
    tablet_count: float | None = None
    total_dose_mg: float | None = None
    weight_kg: float | None = None
    dose_mg_per_kg: float | None = None
    time_window_hours: float | None = None
    ingestion_pattern: str = "unknown"  # "single_acute", "staggered", "chronic_repeated", "unknown"
    time_since_ingestion: str = "unknown"  # "<1h", "1-4h", "4-8h", ">8h", "unknown"
    risk_level: str = "MODERATE"  # "HIGH", "MODERATE", "LOW"
    urgency: str = "URGENT"  # "EMERGENCY", "URGENT", "ROUTINE"
    clinical_rationale: str = ""
    triage_recommendation: str = ""
    clarifying_questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "drug": self.drug,
            "tablet_strength_mg": self.tablet_strength_mg,
            "tablet_count": self.tablet_count,
            "total_dose_mg": self.total_dose_mg,
            "weight_kg": self.weight_kg,
            "dose_mg_per_kg": round(self.dose_mg_per_kg, 2) if self.dose_mg_per_kg is not None else None,
            "ingestion_pattern": self.ingestion_pattern,
            "time_since_ingestion": self.time_since_ingestion,
            "risk_level": self.risk_level,
            "urgency": self.urgency,
            "clinical_rationale": self.clinical_rationale,
        }


# Known aliases for common over-the-counter analgesics
_PARACETAMOL_ALIASES: tuple[str, ...] = (
    "paracetamol",
    "acetaminophen",
    "panadol",
    "efferalgan",
    "tylenol",
    "hapacol",
    "decolgen",
    "para",
    "apap",
)


def extract_paracetamol_dose_assessment(text: str) -> DoseAssessment | None:
    """Analyze paracetamol/acetaminophen ingestion narrative with dose reasoning.
    
    Clinical Toxicology Principles (Rumack-Matthew / FDA / NHS):
      - Standard adult therapeutic ceiling: 4000 mg/24h (max 1000 mg per single dose).
      - Single acute toxic threshold (adult): >= 4000-5000 mg (or >= 150 mg/kg, whichever is lower).
      - Single acute toxic threshold (pediatric): >= 150 mg/kg.
      - Staggered supratherapeutic ingestion (> 4000 mg over 24h): Moderate-to-High risk requiring poison assessment.
      - Triage disposition: Urgent ED/Poison assessment, dose/time establishment, serum APAP testing by clinicians.
    """
    norm = normalize_search_text(text)

    # 1. Check if paracetamol is mentioned
    has_paracetamol = any(
        re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", norm)
        for alias in _PARACETAMOL_ALIASES
    )
    if not has_paracetamol:
        return None

    # Check for ingestion markers
    ingestion_markers = (
        "uong", "da uong", "vua uong", "lo uong", "nham", "uong nham",
        "qua lieu", "boc uong", "uong sach", "uong ca vi", "uong het vi",
        "uong nhieu", "uong lien", "dung", "uong kem"
    )
    if not any(marker in norm for marker in ingestion_markers):
        return None

    # 2. Extract tablet strength (mg)
    tablet_strength_mg: float | None = None
    strength_match = re.search(r"\b(\d{3,4})\s*(?:mg|miligram)\b", norm)
    if strength_match:
        tablet_strength_mg = float(strength_match.group(1))
    elif "extra" in norm:
        tablet_strength_mg = 500.0  # Panadol Extra active paracetamol component
    else:
        # Standard adult OTC formulation default if unspecified
        tablet_strength_mg = 500.0

    # 3. Extract tablet count (negation-aware) with interval support [min, max]
    tablet_count: float | None = None
    tablet_count_min: float | None = None
    tablet_count_max: float | None = None

    # Check for range pattern: e.g., "6-12 vien", "6 den 12 vien", "tu 6 toi 12 vien"
    range_match = re.search(
        r"\b(?:tu\s*)?(\d+(?:[.,]\d+)?)\s*(?:-|den|toi|hay|hoac)\s*(\d+(?:[.,]\d+)?)\s*(?:vien|v|vi|goi|ong)\b",
        norm,
    )
    if range_match:
        c1 = float(range_match.group(1).replace(",", "."))
        c2 = float(range_match.group(2).replace(",", "."))
        tablet_count_min = min(c1, c2)
        tablet_count_max = max(c1, c2)
        tablet_count = tablet_count_max  # Conservative worst-case
    else:
        count_matches = list(re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*(?:vien|v|vi|goi|ong)\b", norm))
        affirmed_counts = []
        for m in count_matches:
            start_pos = m.start()
            prefix = norm[max(0, start_pos - 25):start_pos]
            if any(neg in prefix for neg in ("khong phai", "khong dung", "khong uong", "chua uong")):
                continue
            affirmed_counts.append(float(m.group(1).replace(",", ".")))

        if affirmed_counts:
            # Multi-dose combination: sum if different medicines reported, or take maximum affirmed
            tablet_count = sum(affirmed_counts) if len(affirmed_counts) > 1 and "va" in norm else max(affirmed_counts)
            tablet_count_min = min(affirmed_counts)
            tablet_count_max = tablet_count
        elif any(k in norm for k in ("ca vi", "het vi", "sach tron vi", "ca 1 vi", "nguyen vi", "boc sach", "sach tron")):
            tablet_count = 10.0
            tablet_count_min = 10.0
            tablet_count_max = 10.0
        elif "nua vi" in norm:
            tablet_count = 5.0
            tablet_count_min = 5.0
            tablet_count_max = 5.0
        elif count_matches:
            tablet_count = float(count_matches[-1].group(1).replace(",", "."))
            tablet_count_min = tablet_count
            tablet_count_max = tablet_count

    # 4. Extract total dose in mg or g if mentioned directly (negation-aware)
    total_dose_mg: float | None = None
    gram_matches = list(re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*(?:g|gam|gram)\b", norm))
    affirmed_grams = []
    for m in gram_matches:
        prefix = norm[max(0, m.start() - 25):m.start()]
        if not any(neg in prefix for neg in ("khong phai", "khong uong", "chua uong")):
            affirmed_grams.append(float(m.group(1).replace(",", ".")) * 1000.0)

    if affirmed_grams:
        total_dose_mg = max(affirmed_grams)
    else:
        mg_matches = list(re.finditer(r"\b(\d{4,5})\s*mg\b", norm))
        affirmed_mgs = []
        for m in mg_matches:
            prefix = norm[max(0, m.start() - 25):m.start()]
            if not any(neg in prefix for neg in ("khong phai", "khong uong", "chua uong")):
                affirmed_mgs.append(float(m.group(1)))
        if affirmed_mgs:
            total_dose_mg = max(affirmed_mgs)

    # Calculate total dose if we have tablet count and strength
    if total_dose_mg is None and tablet_count is not None and tablet_strength_mg is not None:
        total_dose_mg = tablet_count * tablet_strength_mg

    # 5. Extract patient weight (kg)
    weight_kg: float | None = None
    weight_match = re.search(
        r"\b(?:nang|can nang|be|em be|chau|tre|nguoi|benh nhan)?\s*(\d+(?:[.,]\d+)?)\s*(?:kg|ki|can)\b",
        norm,
    )
    if weight_match:
        weight_kg = float(weight_match.group(1).replace(",", "."))

    # 6. Extract Ingestion Pattern
    ingestion_pattern = "single_acute"
    if any(k in norm for k in ("trong 24 gio", "trong ngay", "24h", "rai rac", "chia lam", "cach nhau", "tu sang den toi")):
        ingestion_pattern = "staggered"
    elif any(k in norm for k in ("mot lan", "cung luc", "sach tron tu luc nay", "vua uong", "mot luc", "uong het")):
        ingestion_pattern = "single_acute"

    # 7. Extract Time Since Ingestion
    time_since_ingestion = "unknown"
    time_window_hours: float | None = None
    if any(k in norm for k in ("vua uong", "tu luc nay", "moi uong", "cach day 10 phut", "cach day 15 phut", "cach day 30 phut")):
        time_since_ingestion = "<1h"
        time_window_hours = 0.5
    else:
        hours_match = re.search(r"\bcach day\s*(\d+(?:[.,]\d+)?)\s*(?:tieng|gio)\b", norm)
        if hours_match:
            time_window_hours = float(hours_match.group(1).replace(",", "."))
            if time_window_hours <= 1.0:
                time_since_ingestion = "<1h"
            elif time_window_hours <= 4.0:
                time_since_ingestion = "1-4h"
            elif time_window_hours <= 8.0:
                time_since_ingestion = "4-8h"
            else:
                time_since_ingestion = ">8h"

    # Compute mg/kg if weight is available
    dose_mg_per_kg: float | None = None
    if total_dose_mg is not None and weight_kg is not None and weight_kg > 0:
        dose_mg_per_kg = total_dose_mg / weight_kg

    # 8. Clinical Toxicological Risk Stratification
    risk_level = "MODERATE"
    urgency = "URGENT"
    rationale_parts = []

    # Evaluation logic
    if dose_mg_per_kg is not None:
        rationale_parts.append(f"Cân nặng: {weight_kg} kg, Tổng liều: {total_dose_mg:.0f} mg ({dose_mg_per_kg:.1f} mg/kg).")
        if ingestion_pattern == "single_acute":
            if dose_mg_per_kg >= 150.0:
                risk_level = "HIGH"
                urgency = "EMERGENCY"
                rationale_parts.append(
                    f"Liều cấp tính {dose_mg_per_kg:.1f} mg/kg đạt hoặc vượt ngưỡng độc tính gan cấp tính (>= 150 mg/kg), nguy cơ tổn thương gan cấp đe dọa tính mạng."
                )
            elif dose_mg_per_kg >= 75.0 or (total_dose_mg is not None and total_dose_mg >= 4000.0):
                risk_level = "HIGH"
                urgency = "EMERGENCY"
                rationale_parts.append(
                    f"Liều cấp tính {dose_mg_per_kg:.1f} mg/kg hoặc tổng liều >= 4000 mg vượt quá trần dung nạp an toàn, cần chuyển cấp cứu ngay để đánh giá chống độc."
                )
            elif dose_mg_per_kg >= 60.0 or (total_dose_mg is not None and total_dose_mg > 2000.0):
                risk_level = "MODERATE"
                urgency = "URGENT"
                rationale_parts.append(
                    f"Liều cấp tính {dose_mg_per_kg:.1f} mg/kg vượt liều đơn khuyến cáo (10-15 mg/kg), cần liên hệ trung tâm chống độc/cơ sở y tế để theo dõi."
                )
            else:
                risk_level = "LOW"
                urgency = "ROUTINE"
                rationale_parts.append(f"Liều dùng {dose_mg_per_kg:.1f} mg/kg nằm trong giới hạn điều trị thông thường.")
        else:  # staggered / repeated
            if total_dose_mg is not None and total_dose_mg > 4000.0:
                risk_level = "MODERATE"
                urgency = "URGENT"
                rationale_parts.append(
                    f"Uống rải rác tổng cộng {total_dose_mg:.0f} mg trong 24 giờ vượt trần điều trị tối đa hàng ngày (4000 mg/24h), cần đánh giá nguy cơ độc tính tích lũy."
                )
            else:
                risk_level = "LOW"
                urgency = "ROUTINE"
                rationale_parts.append("Liều dùng rải rác trong giới hạn điều trị an toàn hàng ngày.")

    elif total_dose_mg is not None:
        rationale_parts.append(f"Tổng liều ước tính: {total_dose_mg:.0f} mg (chưa rõ cân nặng).")
        if ingestion_pattern == "single_acute":
            if total_dose_mg >= 4000.0:
                # Acute single ingestion >= 4000 mg (e.g. 8-10+ tablets of 500mg, or 12x 325mg = 3900-4000mg)
                risk_level = "HIGH"
                urgency = "EMERGENCY"
                rationale_parts.append(
                    f"Uống cấp tính một lần >= {total_dose_mg:.0f} mg chạm hoặc vượt trần điều trị tối đa cả ngày của người lớn trong một lần uống duy nhất. "
                    "Đối với bất kỳ người bệnh nào dưới 53 kg, liều này đã vượt ngưỡng nguy cơ 75-150 mg/kg."
                )
            elif total_dose_mg >= 2500.0:
                # Single acute bolus 2.5g - 4.0g without weight: high potential toxicity if low weight or pediatric
                risk_level = "HIGH"
                urgency = "EMERGENCY"
                rationale_parts.append(
                    f"Uống cấp tính một lần {total_dose_mg:.0f} mg là liều quá mức rất cao trong một lần (ngưỡng tối đa 1 lần là 1000 mg). "
                    "Cần đánh giá cấp cứu ngay để kiểm tra thời điểm uống và xác định nồng độ thuốc."
                )
            elif total_dose_mg > 1000.0:
                risk_level = "MODERATE"
                urgency = "URGENT"
                rationale_parts.append(
                    f"Liều uống {total_dose_mg:.0f} mg vượt liều đơn khuyến cáo (tối đa 1000 mg/lần), cần tham vấn y tế/chống độc để theo dõi."
                )
            else:
                risk_level = "LOW"
                urgency = "ROUTINE"
                rationale_parts.append("Liều dùng nằm trong giới hạn điều trị thông thường.")
        else:  # staggered
            if total_dose_mg > 4000.0:
                risk_level = "MODERATE"
                urgency = "URGENT"
                rationale_parts.append(
                    f"Tổng lượng paracetamol uống trong ngày đạt {total_dose_mg:.0f} mg, vượt quá ngưỡng 4000 mg/24h. Cần ngừng thuốc ngay và liên hệ cơ sở y tế đánh giá."
                )
            else:
                risk_level = "LOW"
                urgency = "ROUTINE"
                rationale_parts.append("Liều dùng rải rác trong giới hạn điều trị an toàn hàng ngày.")
    else:
        # Dose could not be calculated precisely, but high quantity or acute ingestion reported
        if any(k in norm for k in ("uong sach tron", "ca vi", "uong ca vi", "nhieu vien", "qua lieu rat nhieu")):
            risk_level = "HIGH"
            urgency = "EMERGENCY"
            rationale_parts.append(
                "Báo cáo uống toàn bộ vỉ thuốc hoặc số lượng lớn cấp tính, tiềm ẩn nguy cơ ngộ độc cấp tính nặng cần xử trí khẩn cấp."
            )
        else:
            risk_level = "MODERATE"
            urgency = "URGENT"
            rationale_parts.append(
                "Báo cáo quá liều hoặc uống nhầm thuốc chưa xác định được chính xác số lượng và hàm lượng, cần phân luồng khẩn trương tới cơ sở y tế/trung tâm chống độc."
            )

    clinical_rationale = " ".join(rationale_parts)

    # 9. Formulate Triage Recommendation strictly adhering to Triage vs Treatment separation
    if urgency == "EMERGENCY":
        triage_recommendation = (
            "CẢNH BÁO QUÁ LIỀU CẦN ĐÁNH GIÁ CẤP CỨU:\n"
            f"Thông tin bạn cung cấp cho thấy tình trạng uống paracetamol liều cao nguy cơ ngộ độc cấp tính ({clinical_rationale}).\n\n"
            "HƯỚNG DẪN XỬ TRÍ PHÂN LUỒNG (TRIAGE DISPOSITION):\n"
            "1. GỌI NGAY CẤP CỨU 115 HOẶC ĐẾN NGAY KHOA CẤP CỨU / TRUNG TÂM CHỐNG ĐỘC GẦN NHẤT.\n"
            "2. Mang theo toàn bộ bao bì, vỉ thuốc hoặc chai thuốc đã dùng để bác sĩ xác định chính xác hoạt chất, hàm lượng và tổng liều.\n"
            "3. Xác định mốc thời gian chính xác từ lúc uống thuốc (thời điểm uống viên đầu tiên và viên cuối cùng).\n"
            "4. Các bác sĩ điều trị và chuyên gia chống độc sẽ thăm khám, định lượng nồng độ paracetamol trong máu (nếu phù hợp thời điểm) và quyết định các biện pháp can thiệp y khoa cần thiết.\n"
            "5. Tuyệt đối KHÔNG tự gây nôn tại nhà và không chờ đợi đến khi xuất hiện triệu chứng đau bụng, buồn nôn hay vàng da mới đi khám."
        )
    elif urgency == "URGENT":
        triage_recommendation = (
            "CẢNH BÁO QUÁ LIỀU / SỬ DỤNG THUỐC VƯỢT KHUYẾN CÁO:\n"
            f"Bạn đã báo cáo sử dụng paracetamol vượt ngưỡng thông thường ({clinical_rationale}).\n\n"
            "HƯỚNG DẪN XỬ TRÍ PHÂN LUỒNG:\n"
            "1. Ngừng ngay lập tức việc dùng thêm paracetamol hoặc bất kỳ thuốc cảm sốt/giảm đau phối hợp nào khác.\n"
            "2. Hãy liên hệ ngay cơ sở y tế, trung tâm chống độc hoặc đường dây nóng y tế để được nhân viên y tế đánh giá nguy cơ.\n"
            "3. Mang theo toàn bộ vỏ thuốc và ghi lại chính xác thời gian đã uống thuốc.\n"
            "4. Tuyệt đối không tự gây nôn tại nhà."
        )
    else:
        triage_recommendation = (
            "Liều lượng paracetamol bạn báo cáo nằm trong phạm vi điều trị thông thường. "
            "Hãy đảm bảo không uống quá 1000 mg cho mỗi lần uống và không vượt quá 4000 mg trong vòng 24 giờ. "
            "Nếu triệu chứng sốt hoặc đau không cải thiện sau 3 ngày, hãy đến khám bác sĩ."
        )

    clarifying_questions = [
        "Bạn uống thuốc chính xác cách đây bao nhiêu phút hoặc mấy giờ?",
        "Người uống thuốc bao nhiêu tuổi và cân nặng khoảng bao nhiêu kg?",
        "Thuốc bạn uống chính xác là loại nào (ví dụ Panadol 500mg, Efferalgan 500mg, Panadol Extra) và còn giữ vỏ thuốc không?",
        "Bạn uống cùng lúc một lần hay chia làm nhiều lần trong ngày?",
    ]

    return DoseAssessment(
        drug="paracetamol",
        tablet_strength_mg=tablet_strength_mg,
        tablet_count=tablet_count,
        total_dose_mg=total_dose_mg,
        weight_kg=weight_kg,
        dose_mg_per_kg=dose_mg_per_kg,
        time_window_hours=time_window_hours,
        ingestion_pattern=ingestion_pattern,
        time_since_ingestion=time_since_ingestion,
        risk_level=risk_level,
        urgency=urgency,
        clinical_rationale=clinical_rationale,
        triage_recommendation=triage_recommendation,
        clarifying_questions=clarifying_questions,
    )


def evaluate_dose_reasoning(text: str) -> DoseAssessment | None:
    """Entry point for general medication dose reasoning."""
    # Check paracetamol / acetaminophen
    apap_assessment = extract_paracetamol_dose_assessment(text)
    if apap_assessment is not None:
        return apap_assessment
    return None
