"""Bounded medication-dose reasoning for MedGuard AI.

This module is a toxicology *incident* reasoner, not a general medication-use
classifier.  A medicine name plus an ordinary therapeutic-use statement (for
example, "đã uống paracetamol nhưng vẫn sốt") is insufficient evidence of an
overdose.  Dose reasoning activates only when the user supplies a quantified
dose/tablet count or an explicit overdose/accidental-ingestion signal.

The output is triage disposition only.  It does not prescribe antidotes or
invasive treatment.
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
    ingestion_pattern: str = "unknown"
    time_since_ingestion: str = "unknown"
    risk_level: str = "MODERATE"
    urgency: str = "URGENT"
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

# Explicit toxicology/accidental-ingestion language.  Deliberately excludes
# generic markers such as "uống", "đã uống", "dùng", and "uống kèm".
_TOXICOLOGY_MARKERS: tuple[str, ...] = (
    "qua lieu",
    "lo uong",
    "lo tay uong",
    "uong nham",
    "nham thuoc",
    "uong nhieu",
    "nhieu vien",
    "uong ca vi",
    "uong het vi",
    "uong sach",
    "sach tron vi",
    "nguyen vi",
    "nua vi",
    "boc sach",
    "uong mot luc",
    "uong cung luc",
    "cung mot luc",
)

_COUNT_PATTERN = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(?:vien|v|vi|goi|ong)\b")
_RANGE_PATTERN = re.compile(
    r"\b(?:tu\s*)?(\d+(?:[.,]\d+)?)\s*(?:-|den|toi|hay|hoac)\s*"
    r"(\d+(?:[.,]\d+)?)\s*(?:vien|v|vi|goi|ong)\b"
)
_DIRECT_GRAM_PATTERN = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(?:g|gam|gram)\b")
_DIRECT_TOTAL_MG_PATTERN = re.compile(r"\b(\d{4,5})\s*mg\b")
_STRENGTH_PATTERN = re.compile(r"\b(\d{3,4})\s*(?:mg|miligram)\b")


def _has_quantified_or_toxicology_signal(norm: str) -> bool:
    """Return True only when the narrative actually supports dose/toxicology reasoning."""
    if any(marker in norm for marker in _TOXICOLOGY_MARKERS):
        return True
    if _COUNT_PATTERN.search(norm) or _RANGE_PATTERN.search(norm):
        return True
    # Direct totals such as "uống 5g paracetamol" or "uống 2500 mg" are dose
    # evidence.  A product strength such as "paracetamol 500mg" alone is not:
    # only 4-5 digit mg values are treated as a direct total here.
    if _DIRECT_GRAM_PATTERN.search(norm) or _DIRECT_TOTAL_MG_PATTERN.search(norm):
        return True
    return False


def _affirmed_number_matches(norm: str, pattern: re.Pattern[str]) -> list[re.Match[str]]:
    matches: list[re.Match[str]] = []
    for match in pattern.finditer(norm):
        prefix = norm[max(0, match.start() - 30):match.start()]
        if any(neg in prefix for neg in ("khong phai", "khong dung", "khong uong", "chua uong")):
            continue
        matches.append(match)
    return matches


def extract_paracetamol_dose_assessment(text: str) -> DoseAssessment | None:
    """Analyze a *supported* paracetamol ingestion incident.

    The activation gate is intentionally strict to keep ordinary medication
    questions in the medication-safety pipeline rather than fabricating an
    overdose from an unknown therapeutic dose.
    """
    norm = normalize_search_text(text)
    has_paracetamol = any(
        re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", norm)
        for alias in _PARACETAMOL_ALIASES
    )
    if not has_paracetamol or not _has_quantified_or_toxicology_signal(norm):
        return None

    # Tablet strength is formulation information, not by itself an overdose
    # signal.  It is used only after the activation gate above has passed.
    strength_match = _STRENGTH_PATTERN.search(norm)
    if strength_match:
        tablet_strength_mg = float(strength_match.group(1))
    elif "extra" in norm:
        tablet_strength_mg = 500.0
    else:
        tablet_strength_mg = 500.0

    tablet_count: float | None = None
    range_match = _RANGE_PATTERN.search(norm)
    if range_match:
        c1 = float(range_match.group(1).replace(",", "."))
        c2 = float(range_match.group(2).replace(",", "."))
        tablet_count = max(c1, c2)
    else:
        count_matches = _affirmed_number_matches(norm, _COUNT_PATTERN)
        counts = [float(match.group(1).replace(",", ".")) for match in count_matches]
        if counts:
            tablet_count = sum(counts) if len(counts) > 1 and " va " in f" {norm} " else max(counts)
        elif any(marker in norm for marker in ("ca vi", "het vi", "sach tron vi", "nguyen vi", "boc sach")):
            tablet_count = 10.0
        elif "nua vi" in norm:
            tablet_count = 5.0

    total_dose_mg: float | None = None
    gram_matches = _affirmed_number_matches(norm, _DIRECT_GRAM_PATTERN)
    if gram_matches:
        total_dose_mg = max(float(m.group(1).replace(",", ".")) * 1000.0 for m in gram_matches)
    else:
        total_mg_matches = _affirmed_number_matches(norm, _DIRECT_TOTAL_MG_PATTERN)
        if total_mg_matches:
            total_dose_mg = max(float(m.group(1)) for m in total_mg_matches)

    if total_dose_mg is None and tablet_count is not None:
        total_dose_mg = tablet_count * tablet_strength_mg

    weight_kg: float | None = None
    weight_match = re.search(
        r"\b(?:nang|can nang|be|em be|chau|tre|nguoi|benh nhan|nguoi lon)?\s*"
        r"(\d+(?:[.,]\d+)?)\s*(?:kg|ki|can)\b",
        norm,
    )
    if weight_match:
        weight_kg = float(weight_match.group(1).replace(",", "."))

    ingestion_pattern = "single_acute"
    if any(k in norm for k in ("trong 24 gio", "trong ngay", "24h", "rai rac", "chia lam", "cach nhau", "tu sang den toi")):
        ingestion_pattern = "staggered"

    time_since_ingestion = "unknown"
    time_window_hours: float | None = None
    if any(k in norm for k in ("vua uong", "moi uong", "cach day 10 phut", "cach day 15 phut", "cach day 30 phut", "tu luc nay")):
        time_since_ingestion = "<1h"
        time_window_hours = 0.5
    else:
        hours_match = re.search(r"\bcach day\s*(\d+(?:[.,]\d+)?)\s*(?:tieng|gio)\b", norm)
        if hours_match:
            time_window_hours = float(hours_match.group(1).replace(",", "."))
            if time_window_hours <= 1:
                time_since_ingestion = "<1h"
            elif time_window_hours <= 4:
                time_since_ingestion = "1-4h"
            elif time_window_hours <= 8:
                time_since_ingestion = "4-8h"
            else:
                time_since_ingestion = ">8h"

    dose_mg_per_kg = (
        total_dose_mg / weight_kg
        if total_dose_mg is not None and weight_kg is not None and weight_kg > 0
        else None
    )

    risk_level = "MODERATE"
    urgency = "URGENT"
    rationale_parts: list[str] = []

    if dose_mg_per_kg is not None and total_dose_mg is not None:
        rationale_parts.append(
            f"Cân nặng: {weight_kg:g} kg, tổng liều ước tính: {total_dose_mg:.0f} mg "
            f"({dose_mg_per_kg:.1f} mg/kg)."
        )
        if ingestion_pattern == "staggered":
            if total_dose_mg > 4000:
                risk_level, urgency = "MODERATE", "URGENT"
                rationale_parts.append("Tổng lượng báo cáo trong 24 giờ vượt giới hạn điều trị thông thường và cần được đánh giá y tế.")
            else:
                risk_level, urgency = "LOW", "ROUTINE"
                rationale_parts.append("Tổng lượng được báo cáo chưa vượt ngưỡng sàng lọc của nhánh quá liều này.")
        elif dose_mg_per_kg >= 150 or dose_mg_per_kg >= 75 or total_dose_mg >= 4000:
            risk_level, urgency = "HIGH", "EMERGENCY"
            rationale_parts.append("Liều cấp tính được báo cáo đủ cao để cần đánh giá cấp cứu/ngộ độc ngay, thay vì chờ triệu chứng xuất hiện.")
        elif dose_mg_per_kg >= 60 or total_dose_mg > 2000:
            risk_level, urgency = "MODERATE", "URGENT"
            rationale_parts.append("Liều báo cáo vượt mức dùng đơn thông thường; cần tham vấn y tế/chống độc sớm.")
        else:
            risk_level, urgency = "LOW", "ROUTINE"
            rationale_parts.append("Liều được báo cáo nằm dưới ngưỡng cảnh báo của bộ phân luồng quá liều này.")

    elif total_dose_mg is not None:
        rationale_parts.append(f"Tổng liều ước tính: {total_dose_mg:.0f} mg; chưa rõ cân nặng.")
        if ingestion_pattern == "staggered":
            if total_dose_mg > 4000:
                risk_level, urgency = "MODERATE", "URGENT"
                rationale_parts.append("Tổng lượng trong 24 giờ vượt giới hạn điều trị thông thường.")
            else:
                risk_level, urgency = "LOW", "ROUTINE"
                rationale_parts.append("Tổng lượng báo cáo chưa vượt ngưỡng sàng lọc của nhánh quá liều này.")
        elif total_dose_mg >= 2500:
            risk_level, urgency = "HIGH", "EMERGENCY"
            rationale_parts.append("Đây là lượng cao cho một lần dùng; cần đánh giá cấp cứu/chống độc để xác minh nguy cơ theo cân nặng và thời điểm uống.")
        elif total_dose_mg > 1000:
            risk_level, urgency = "MODERATE", "URGENT"
            rationale_parts.append("Lượng dùng một lần vượt mức đơn thông thường; cần được đánh giá y tế/chống độc sớm.")
        else:
            risk_level, urgency = "LOW", "ROUTINE"
            rationale_parts.append("Lượng báo cáo nằm trong phạm vi điều trị thông thường của nhánh sàng lọc này.")

    elif any(marker in norm for marker in ("uong sach", "ca vi", "uong ca vi", "uong het vi", "nhieu vien", "qua lieu rat nhieu")):
        risk_level, urgency = "HIGH", "EMERGENCY"
        rationale_parts.append("Người dùng báo cáo một lượng lớn/không xác định, nên phải xử lý như một phơi nhiễm có nguy cơ cho tới khi được xác minh.")
    else:
        # Explicit accidental/overdose wording is present, but the quantity is
        # unknown.  Asking for dose/time is appropriate; ordinary therapeutic
        # use cannot reach this branch because of the activation gate.
        risk_level, urgency = "MODERATE", "URGENT"
        rationale_parts.append("Có tín hiệu uống nhầm/quá liều nhưng chưa đủ số lượng, hàm lượng hoặc thời điểm để định lượng nguy cơ.")

    clinical_rationale = " ".join(rationale_parts)

    if urgency == "EMERGENCY":
        triage_recommendation = (
            "Cần đánh giá cấp cứu/ngộ độc ngay. Gọi 115 hoặc đến khoa Cấp cứu/trung tâm chống độc gần nhất; "
            "mang theo bao bì hoặc vỉ thuốc và ghi lại thời điểm, số lượng đã uống. Không tự gây nôn và không chờ xuất hiện triệu chứng mới đi khám."
        )
    elif urgency == "URGENT":
        triage_recommendation = (
            "Không dùng thêm paracetamol hoặc thuốc phối hợp có chứa paracetamol cho tới khi đã xác minh tổng liều. "
            "Liên hệ cơ sở y tế/trung tâm chống độc hoặc dược sĩ-bác sĩ sớm; chuẩn bị thông tin về số viên, hàm lượng, thời điểm uống và cân nặng. Không tự gây nôn."
        )
    else:
        triage_recommendation = (
            "Không có tín hiệu quá liều rõ từ lượng đã khai báo. Tiếp tục tuân theo nhãn thuốc/đơn đang dùng; "
            "nếu còn không chắc tổng liều trong 24 giờ hoặc có bệnh gan, uống rượu nhiều, đang dùng thuốc phối hợp, hãy hỏi bác sĩ hoặc dược sĩ trước khi dùng thêm."
        )

    clarifying_questions = [
        "Bạn đã uống chính xác bao nhiêu viên hoặc tổng bao nhiêu mg/g?",
        "Hàm lượng mỗi viên là bao nhiêu và thuốc có chứa thêm hoạt chất nào khác không?",
        "Bạn uống một lần hay chia nhiều lần, và lần gần nhất cách đây bao lâu?",
        "Người uống bao nhiêu tuổi, cân nặng khoảng bao nhiêu và có bệnh gan/uống rượu nhiều không?",
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
    return extract_paracetamol_dose_assessment(text)
