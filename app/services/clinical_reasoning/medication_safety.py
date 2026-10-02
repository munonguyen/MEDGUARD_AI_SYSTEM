"""Medication safety pipeline and clinical contraindication guard.

Ensures that pain or symptom queries do not lead to automatic drug prescriptions,
and enforces critical safety checks regarding allergies, substance interactions,
and medical contraindications.
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


class MedicationSafetyPipeline:
    """Multi-step medication safety validator before any drug advice is rendered."""

    def evaluate(
        self,
        query: str,
        patient_context: dict[str, Any] | None = None,
    ) -> MedicationSafetyResult:
        norm = normalize_search_text(query)
        context = dict(patient_context or {})
        warnings: list[str] = []
        contraindications: list[str] = []

        # 1. Alcohol + Sedatives / Sleeping Pills interaction check
        alcohol_present = bool(re.search(r"\b(?:uong ruou|uong bia|co con|nhau)\b", norm))
        sedative_requested = bool(re.search(r"\b(?:thuoc ngu|thuoc an than|buon ngu|thuoc giup ngu|sedative)\b", norm))

        if alcohol_present and sedative_requested:
            contraindications.append("alcohol_sedative_coadministration")
            warnings.append(
                "Tuyệt đối không sử dụng thuốc ngủ hay thuốc an thần cùng rượu bia do tương tác ức chế thần kinh trung ương và suy hô hấp nguy hiểm."
            )
            return MedicationSafetyResult(
                allowed=False,
                warning_notes=warnings,
                contraindications_detected=contraindications,
                guidance=(
                    "Không được uống thuốc ngủ sau khi đã uống rượu bia. Rượu làm tăng mạnh tác dụng ức chế thần kinh của thuốc, "
                    "có nguy cơ gây ngủ sâu bất thường, ngừng thở khi ngủ hoặc suy hô hấp. Hãy nghỉ ngơi, uống nước lọc và theo dõi."
                ),
            )

        # 2. Antibiotic / Cross-allergy check (Penicillin -> Amoxicillin)
        has_penicillin_allergy = bool(re.search(r"\b(?:di ung penicillin|di ung beta lactam|tung di ung penicillin)\b", norm))
        taking_amoxicillin = bool(re.search(r"\b(?:amoxicillin|augmentin|amox|thuoc khang sinh)\b", norm))

        if has_penicillin_allergy and taking_amoxicillin:
            contraindications.append("penicillin_amoxicillin_cross_reactivity")
            warnings.append(
                "Người có tiền sử dị ứng Penicillin có nguy cơ cao dị ứng chéo với Amoxicillin (nhóm beta-lactam)."
            )
            return MedicationSafetyResult(
                allowed=False,
                warning_notes=warnings,
                contraindications_detected=contraindications,
                guidance=(
                    "Amoxicillin thuộc cùng nhóm kháng sinh Penicillin. Người có tiền sử dị ứng penicillin (đặc biệt từng nổi mề đay toàn thân) "
                    "tuyệt đối không được tự ý dùng thử hay uống nửa viên vì nguy cơ xuất hiện phản vệ tái phát nặng hơn. "
                    "Hãy liên hệ ngay bác sĩ kê đơn để được đổi sang nhóm kháng sinh an toàn thay thế."
                ),
            )

        # 3. Anticoagulants and bleeding
        anticoagulant_user = bool(re.search(r"\b(?:chong dong|aspirin|warfarin|xarelto|eliquis|clopidogrel)\b", norm))
        bleeding_complaint = bool(re.search(r"\b(?:chay mau cam|chay mau|xuat huyet)\b", norm))
        altering_dose = bool(re.search(r"\b(?:bo lieu|ngung thuoc|giam lieu|tu bo)\b", norm))

        if anticoagulant_user and altering_dose:
            contraindications.append("unauthorized_anticoagulant_cessation")
            warnings.append(
                "Không tự ý ngừng hoặc bỏ liều thuốc chống đông mà không có chỉ định chuyên khoa của bác sĩ tim mạch."
            )
            return MedicationSafetyResult(
                allowed=False,
                warning_notes=warnings,
                contraindications_detected=contraindications,
                guidance=(
                    "Bạn không nên tự ý bỏ hoặc ngừng thuốc chống đông vì việc ngưng đột ngột có thể làm tăng nguy cơ tắc mạch hay huyết khối. "
                    "Nếu đang bị chảy máu kéo dài hoặc tái phát, hãy đến cơ sở y tế để được bác sĩ kiểm tra và điều chỉnh liều an toàn."
                ),
            )

        # 4. Routine pain queries: enforce education rather than autonomous prescribing
        pain_complaint = bool(re.search(r"\b(?:dau co|dau lung|dau dau|dau nguc|dau bung|moi co|cang co)\b", norm))
        if pain_complaint:
            guidance = (
                "MedGuard cung cấp thông tin y tế tham khảo, không tự động kê đơn hay chỉ định liều dùng thuốc cá nhân hóa. "
                "Đối với các tình trạng đau cơ học nhẹ, nên ưu tiên các biện pháp không dùng thuốc (nghỉ ngơi, kéo giãn nhẹ, chườm ấm/mát). "
                "Nếu cần dùng thuốc giảm đau không kê đơn, người bệnh cần tham khảo ý kiến dược sĩ/bác sĩ và kiểm tra kỹ bệnh nền (dạ dày, gan, thận)."
            )
            return MedicationSafetyResult(
                allowed=True,
                warning_notes=["non_pharmacological_first_line"],
                contraindications_detected=[],
                guidance=guidance,
            )

        return MedicationSafetyResult(
            allowed=True,
            warning_notes=[],
            contraindications_detected=[],
            guidance="Luôn trao đổi với bác sĩ hoặc dược sĩ trước khi bắt đầu hoặc thay đổi bất kỳ loại thuốc nào.",
        )
