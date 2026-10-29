"""Medication safety pipeline and clinical contraindication guard.

V28.1 evaluates both the current message and bounded patient context before
allowing medication advice to reach the response writer. It does not prescribe;
it identifies hard-stop combinations and situations requiring pharmacist or
clinician review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from app.services.clinical_text import normalize_search_text


@dataclass
class MedicationSafetyResult:
    allowed: bool
    warning_notes: list[str] = field(default_factory=list)
    contraindications_detected: list[str] = field(default_factory=list)
    guidance: str = ""


def _context_text(value: Any) -> str:
    """Normalize list/string/dict context without introducing patient identifiers."""
    if value in (None, "", []):
        return ""
    if isinstance(value, dict):
        parts = [str(v) for v in value.values() if v not in (None, "", [])]
        return normalize_search_text(" ".join(parts))
    if isinstance(value, (list, tuple, set)):
        return normalize_search_text(" ".join(str(v) for v in value if v not in (None, "")))
    return normalize_search_text(str(value))


class MedicationSafetyPipeline:
    """Multi-step medication safety validator before drug advice is rendered."""

    def evaluate(
        self,
        query: str,
        patient_context: dict[str, Any] | None = None,
    ) -> MedicationSafetyResult:
        norm = normalize_search_text(query)
        context = dict(patient_context or {})
        allergy_text = _context_text(context.get("allergies"))
        medication_text = _context_text(context.get("current_medications"))
        condition_text = _context_text(context.get("conditions"))
        combined = " ".join(part for part in (norm, allergy_text, medication_text, condition_text) if part)
        warnings: list[str] = []
        contraindications: list[str] = []
        age = context.get("age")

        # 1. Alcohol + sedatives / sleeping pills.
        alcohol_present = bool(re.search(r"\b(?:uong ruou|uong bia|co con|nhau)\b", norm))
        sedative_present = bool(
            re.search(
                r"\b(?:thuoc ngu|thuoc an than|thuoc gay buon ngu|thuoc giup ngu|buon ngu|benzodiazepine|diazepam|lorazepam|alprazolam|zolpidem|sedative)\b",
                combined,
            )
        )
        if alcohol_present and sedative_present:
            return MedicationSafetyResult(
                allowed=False,
                warning_notes=["alcohol_sedative_cns_depression"],
                contraindications_detected=["alcohol_sedative_coadministration"],
                guidance=(
                    "Không được uống thuốc ngủ sau khi đã uống rượu bia. Không dùng thêm thuốc ngủ hoặc thuốc an thần khi đã uống rượu bia vì sự phối hợp này có thể làm tăng ức chế thần kinh trung ương, gây buồn ngủ sâu và suy hô hấp. "
                    "Nếu đã phối hợp và xuất hiện khó đánh thức, thở chậm hoặc lú lẫn, cần gọi cấp cứu."
                ),
            )

        # 2. Penicillin allergy + amoxicillin/augmentin. Context allergies count;
        # the user does not have to repeat the allergy in the current message.
        has_penicillin_allergy = bool(
            re.search(r"\b(?:penicillin|beta lactam|amoxicillin|augmentin)\b", allergy_text)
            or re.search(r"\b(?:di ung penicillin|tung di ung penicillin|di ung beta lactam)\b", norm)
        )
        amoxicillin_present = bool(
            re.search(r"\b(?:amoxicillin|augmentin|amox)\b", norm + " " + medication_text)
        )
        if has_penicillin_allergy and amoxicillin_present:
            return MedicationSafetyResult(
                allowed=False,
                warning_notes=["penicillin_class_allergy"],
                contraindications_detected=["penicillin_amoxicillin_cross_reactivity"],
                guidance=(
                    "Amoxicillin thuộc nhóm penicillin; khi có tiền sử dị ứng penicillin, tuyệt đối không được tự ý dùng thử hay uống nửa viên để kiểm tra phản ứng. "
                    "Không tự dùng tiếp amoxicillin/augmentin cho đến khi được bác sĩ hoặc dược sĩ đánh giá. Nếu hiện có sưng môi/lưỡi, nghẹn họng, khó thở, choáng hoặc nổi mề đay lan nhanh, cần xử trí cấp cứu."
                ),
            )

        # 3. Anticoagulants: do not advise autonomous interruption and flag
        # non-selective NSAID combinations because bleeding risk may increase.
        anticoagulant_user = bool(
            re.search(
                r"\b(?:warfarin|xarelto|rivaroxaban|eliquis|apixaban|clopidogrel|dabigatran|thuoc chong dong)\b",
                combined,
            )
        )
        altering_dose = bool(re.search(r"\b(?:bo lieu|ngung thuoc|giam lieu|tu bo|dung lai thuoc)\b", norm))
        nsaid_requested = bool(
            re.search(r"\b(?:ibuprofen|naproxen|diclofenac|meloxicam|celecoxib|nsaid)\b", norm)
        )
        if anticoagulant_user and altering_dose:
            return MedicationSafetyResult(
                allowed=False,
                warning_notes=["anticoagulant_do_not_change_without_prescriber"],
                contraindications_detected=["unauthorized_anticoagulant_cessation"],
                guidance=(
                    "Bạn không nên tự ý bỏ hoặc ngừng thuốc chống đông vì việc thay đổi đột ngột có thể làm tăng nguy cơ huyết khối ở một số bệnh cảnh. "
                    "Nếu có chảy máu kéo dài, phân đen, nôn ra máu, tiểu máu, choáng hoặc ngất, cần được đánh giá y tế khẩn cấp; việc điều chỉnh thuốc phải do bác sĩ quyết định."
                ),
            )
        if anticoagulant_user and nsaid_requested:
            return MedicationSafetyResult(
                allowed=False,
                warning_notes=["anticoagulant_nsaid_bleeding_risk"],
                contraindications_detected=["anticoagulant_nsaid_combination_requires_review"],
                guidance=(
                    "Không nên tự thêm ibuprofen/naproxen/diclofenac hoặc NSAID khác khi đang dùng thuốc chống đông hay kháng kết tập tiểu cầu. "
                    "Sự phối hợp có thể làm tăng nguy cơ chảy máu; hãy hỏi bác sĩ hoặc dược sĩ về lựa chọn giảm đau phù hợp với thuốc hiện tại."
                ),
            )

        # 4. NSAIDs in selected high-risk conditions.
        nsaid_risk_condition = bool(
            re.search(
                r"\b(?:suy than|benh than|loet da day|xuat huyet tieu hoa|chay mau da day)\b",
                condition_text + " " + norm,
            )
        )
        if nsaid_requested and nsaid_risk_condition:
            return MedicationSafetyResult(
                allowed=False,
                warning_notes=["nsaid_high_risk_comorbidity"],
                contraindications_detected=["nsaid_requires_clinician_review"],
                guidance=(
                    "Không tự dùng NSAID như ibuprofen, naproxen hoặc diclofenac khi có bệnh thận, loét dạ dày hoặc tiền sử xuất huyết tiêu hóa. "
                    "Cần trao đổi với bác sĩ/dược sĩ để chọn phương án giảm đau an toàn hơn."
                ),
            )

        # 5. Aspirin in children/adolescents should not be suggested casually.
        aspirin_requested = bool(re.search(r"\baspirin\b", norm))
        if isinstance(age, int) and age < 18 and aspirin_requested:
            return MedicationSafetyResult(
                allowed=False,
                warning_notes=["aspirin_under_18_requires_clinician"],
                contraindications_detected=["aspirin_pediatric_self_use"],
                guidance=(
                    "Không tự cho người dưới 18 tuổi dùng aspirin để điều trị đau hoặc sốt nếu chưa có chỉ định chuyên môn. Hãy hỏi bác sĩ hoặc dược sĩ về lựa chọn phù hợp theo tuổi và cân nặng."
                ),
            )

        # 6. Pediatric personalized dosing needs weight and professional review.
        asks_personalized_dose = bool(
            re.search(r"\b(?:uong bao nhieu|lieu bao nhieu|may vien|bao nhieu mg|lieu dung)\b", norm)
        )
        if isinstance(age, int) and age < 12 and asks_personalized_dose:
            return MedicationSafetyResult(
                allowed=False,
                warning_notes=["pediatric_dose_requires_weight_and_product"],
                contraindications_detected=["insufficient_pediatric_dosing_context"],
                guidance=(
                    "Không thể đưa liều cá nhân hóa an toàn cho trẻ chỉ từ tuổi. Liều thường phụ thuộc cân nặng, hoạt chất, nồng độ chế phẩm và bệnh nền; cần kiểm tra nhãn thuốc và hỏi bác sĩ/dược sĩ."
                ),
            )

        # 7. Routine pain queries: support self-care first, but do not ban OTC
        # education when no hard contraindication has been found.
        pain_complaint = bool(
            re.search(r"\b(?:dau co|dau lung|dau dau|dau nguc|dau bung|moi co|cang co)\b", norm)
        )
        if pain_complaint:
            return MedicationSafetyResult(
                allowed=True,
                warning_notes=["non_pharmacological_first_line"],
                contraindications_detected=[],
                guidance=(
                    "MedGuard cung cấp thông tin y tế tham khảo, không tự động kê đơn hay chỉ định liều dùng thuốc cá nhân hóa. "
                    "Ưu tiên xử trí theo nguyên nhân và các biện pháp không dùng thuốc khi phù hợp. Nếu cần thuốc không kê đơn, phải kiểm tra tuổi, dị ứng, bệnh gan/thận/dạ dày, thai kỳ và các thuốc đang dùng trước khi lựa chọn hoạt chất hoặc liều."
                ),
            )

        return MedicationSafetyResult(
            allowed=True,
            warning_notes=warnings,
            contraindications_detected=contraindications,
            guidance="Kiểm tra tuổi, dị ứng, bệnh nền và thuốc đang dùng trước khi bắt đầu hoặc thay đổi thuốc; hỏi bác sĩ/dược sĩ khi có yếu tố nguy cơ hoặc chưa chắc chắn.",
        )
