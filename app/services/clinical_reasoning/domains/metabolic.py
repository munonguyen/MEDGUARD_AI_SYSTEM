"""Metabolic and home glucose monitoring clinical reasoning domain."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.services.clinical_text import normalize_search_text
from app.services.clinical_reasoning.domains.headache import DomainAssessment


class MetabolicReasoner:
    """Evaluates blood glucose levels and metabolic symptoms like hypoglycemia."""

    def evaluate(self, text: str, clinical_context: Any) -> DomainAssessment:
        norm = normalize_search_text(text)
        red_flags: list[str] = []

        # Extract numeric glucose value if present
        glucose_val = None
        match = re.search(r"\b(?:duong huyet|glucose)\b[^\d\n]{0,25}?(\d{2,3}(?:\.\d+)?)\s*(?:mg/dl|mg|mmol/l)?", norm)
        if not match:
            match = re.search(r"\b(?:con|la|duoc|do lai|may do)\s*(\d{2,3}(?:\.\d+)?)\s*(?:mg/dl|mg|mg dl)\b", norm)
        if not match:
            match = re.search(r"\b(\d{2,3}(?:\.\d+)?)\s*(?:mg/dl|mg dl)\b", norm)

        if match:
            try:
                glucose_val = float(match.group(1))
            except ValueError:
                pass

        # 1. Severe Neuroglycopenia / Hypoglycemic coma risk (< 54 mg/dL or altered consciousness)
        altered_mental = bool(re.search(r"\b(?:lu lan|kho tra loi|lo mo|noi lap bap|hon me|khong tinh tao)\b", norm))

        if (glucose_val is not None and glucose_val < 54.0) or (altered_mental and ("duong huyet" in norm or "glucose" in norm)):
            red_flags.append("severe_hypoglycemia_neuroglycopenia")
            return DomainAssessment(
                risk_level="EMERGENCY",
                subtype="severe_hypoglycemia_emergency",
                rationale=(
                    f"Chỉ số đường huyết rất thấp{f' ({glucose_val:g} mg/dL)' if glucose_val else ''} kèm dấu hiệu suy giảm ý thức/lú lẫn "
                    "là tình trạng hạ đường huyết nghiêm trọng có nguy cơ tổn thương não hoặc co giật, hôn mê hạ đường huyết."
                ),
                suggested_action="Gọi 115 ngay lập tức. Người nhà cần hỗ trợ nếu bệnh nhân còn nuốt được (ngậm đường/mật ong), không cho ăn uống nếu đã lơ mơ.",
                red_flags=red_flags,
            )

        # 2. Mild-to-Moderate Hypoglycemia (54 - 69 mg/dL) or early adrenergic symptoms
        is_hypo_range = glucose_val is not None and (54.0 <= glucose_val < 70.0)
        has_adrenergic = bool(re.search(r"\b(?:run tay|doi|tim dap nhanh|hoi hop|chong mat|toat mo hoi)\b", norm))

        if is_hypo_range or (has_adrenergic and ("duong huyet" in norm or "glucose" in norm)):
            return DomainAssessment(
                risk_level="URGENT",
                subtype="acute_hypoglycemia_rule_of_15",
                rationale=(
                    f"Đường huyết ở mức thấp{f' ({glucose_val:g} mg/dL)' if glucose_val else ''} đang gây ra phản ứng hạ đường huyết cấp tính. "
                    "Cần bổ sung carbohydrate hấp thu nhanh ngay để tránh tụt đường huyết sâu hơn."
                ),
                suggested_action=(
                    "Áp dụng ngay Quy tắc 15: Nạp 15g đường nhanh (uống 1/2 cốc nước đường/nước ngọt có ga hoặc 3-4 viên đường/kẹo ngọt). "
                    "Nghỉ ngơi 15 phút rồi đo lại đường huyết. Nếu vẫn dưới 70 mg/dL hoặc triệu chứng không giảm, lặp lại 1 lần và liên hệ y tế."
                ),
                red_flags=["mild_hypoglycemia"],
            )

        return DomainAssessment(
            risk_level="ROUTINE",
            subtype="routine_metabolic_monitoring",
            rationale="Chỉ số đường huyết trong khoảng theo dõi hoặc chưa có biểu hiện bất thường nghiêm trọng.",
            suggested_action="Duy trì chế độ ăn uống, theo dõi đường huyết theo kế hoạch và ghi nhật ký đo.",
            red_flags=[],
        )
