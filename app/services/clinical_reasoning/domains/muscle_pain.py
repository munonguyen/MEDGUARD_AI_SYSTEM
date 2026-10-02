"""Muscle pain clinical reasoning domain."""

from __future__ import annotations

import re
from typing import Any

from app.services.clinical_text import normalize_search_text
from app.services.clinical_reasoning.domains.headache import DomainAssessment
from app.services.clinical_reasoning.negation_engine import NegationEngine


class MusclePainReasoner:
    """Evaluate myalgia while separating exercise soreness from high-risk patterns."""

    def __init__(self) -> None:
        self.negation_engine = NegationEngine()

    def _affirmed_regex(self, norm: str, pattern: str) -> bool:
        for match in re.finditer(pattern, norm):
            phrase = match.group(0).strip()
            if phrase and not self.negation_engine.detect(norm, phrase):
                return True
        return False

    def evaluate(self, text: str, clinical_context: Any) -> DomainAssessment:
        norm = normalize_search_text(text)
        positive = getattr(clinical_context, "positive_findings", {}) or {}
        red_flags: list[str] = []

        # 1. Rhabdomyolysis warning signs. They must be affirmed; phrases such
        # as "không có nước tiểu sẫm màu" must not escalate the user.
        dark_urine = self._affirmed_regex(
            norm,
            r"\b(?:nuoc tieu.*(?:mau nau|sam mau|nuoc che|nuoc tra|do sam|mau coca)|tieu it)\b",
        )
        severe_edema_weakness = self._affirmed_regex(
            norm,
            r"\b(?:sung to bat thuong|khong the cu dong|yeu liet co)\b",
        )

        if dark_urine or severe_edema_weakness:
            if dark_urine:
                red_flags.append("dark_tea_colored_urine")
            if severe_edema_weakness:
                red_flags.append("severe_muscle_edema_or_weakness")

            return DomainAssessment(
                risk_level="URGENT",
                subtype="rhabdomyolysis_warning",
                rationale=(
                    "Đau cơ kèm nước tiểu sẫm màu/tiểu ít hoặc sưng-yếu cơ rõ là tổ hợp cần được đánh giá sớm vì có thể gặp trong tiêu cơ vân và các nguyên nhân gây tổn thương cơ-thận khác. "
                    "Tin nhắn không đủ để xác định chẩn đoán."
                ),
                suggested_action=(
                    "Đến cơ sở y tế trong ngày để được khám và cân nhắc xét nghiệm men cơ, điện giải và chức năng thận. "
                    "Nếu tiểu rất ít, lơ mơ, yếu tăng nhanh hoặc tình trạng toàn thân xấu đi, hãy đi cấp cứu."
                ),
                red_flags=red_flags,
            )

        # 2. Delayed-onset muscle soreness requires an actual exercise/overuse
        # trigger. The symptom words "đau cơ/mỏi cơ/căng cơ" alone are not
        # evidence of exercise and must not auto-label every myalgia as DOMS.
        exercise_pattern = bool(positive.get("exercise")) or self._affirmed_regex(
            norm,
            r"\b(?:tap gym|sau tap|sau buoi tap|sau khi tap|chay bo|nang ta|tap ta|tap luyen|van dong nang|choi the thao)\b",
        )

        if exercise_pattern:
            return DomainAssessment(
                risk_level="ROUTINE",
                subtype="exercise_soreness_doms",
                rationale=(
                    "Đau/mỏi cơ xuất hiện sau tập luyện hoặc tăng tải vận động có thể phù hợp với đau cơ sau vận động (DOMS), đặc biệt khi không có dấu hiệu cảnh báo được mô tả như nước tiểu sẫm màu, tiểu ít hoặc yếu-sưng cơ tăng nhanh."
                ),
                suggested_action=(
                    "Giảm cường độ tập trong thời gian ngắn, ngủ đủ, uống nước theo nhu cầu và vận động nhẹ trong ngưỡng chịu được. "
                    "Không cần tự động dùng thuốc giảm đau. Đi khám nếu đau tăng thay vì giảm, kéo dài bất thường, yếu rõ, sưng nhiều hoặc xuất hiện nước tiểu sẫm màu/tiểu ít."
                ),
                red_flags=[],
            )

        return DomainAssessment(
            risk_level="ROUTINE",
            subtype="general_myalgia",
            rationale=(
                "Hiện có mô tả đau/mỏi cơ nhưng chưa có đủ bằng chứng để quy cho tập luyện hay xác định nguyên nhân cụ thể. "
                "Cần dựa thêm vào vị trí, thời điểm khởi phát, sốt, chấn thương, thuốc đang dùng và các triệu chứng toàn thân nếu có."
            ),
            suggested_action=(
                "Nghỉ tương đối, vận động nhẹ trong ngưỡng chịu được và theo dõi. Đi khám nếu đau tăng dần, kéo dài, kèm sốt, yếu rõ, sưng nóng đỏ, nước tiểu sẫm màu hoặc tiểu ít."
            ),
            red_flags=[],
        )
