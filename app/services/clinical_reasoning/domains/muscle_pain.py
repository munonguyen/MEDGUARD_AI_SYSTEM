"""Muscle pain clinical reasoning domain."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.services.clinical_text import normalize_search_text
from app.services.clinical_reasoning.domains.headache import DomainAssessment


class MusclePainReasoner:
    """Evaluates muscle pain presentations to distinguish routine DOMS from rhabdomyolysis."""

    def evaluate(self, text: str, clinical_context: Any) -> DomainAssessment:
        norm = normalize_search_text(text)
        red_flags: list[str] = []

        # 1. Rhabdomyolysis signs
        dark_urine = bool(re.search(r"\b(?:nuoc tieu.*(?:mau nau|sam mau|nuoc che|nuoc tra|do sam|mau coca)|tieu it)\b", norm))
        severe_edema_weakness = bool(re.search(r"\b(?:sung to bat thuong|khong the cu dong|yeu liet co)\b", norm))

        if dark_urine or severe_edema_weakness:
            if dark_urine:
                red_flags.append("dark_tea_colored_urine")
            if severe_edema_weakness:
                red_flags.append("severe_muscle_edema")

            return DomainAssessment(
                risk_level="URGENT",
                subtype="rhabdomyolysis_warning",
                rationale=(
                    "Đau cơ sau vận động nặng kèm theo nước tiểu sẫm màu (nâu hoặc màu nước trà) hoặc sưng cơ rõ "
                    "là dấu hiệu cảnh báo tiêu cơ vân cấp (rhabdomyolysis), có nguy cơ gây tổn thương thận cấp nếu không được bù dịch và kiểm tra kịp thời."
                ),
                suggested_action="Đến ngay cơ sở y tế gần nhất để xét nghiệm máu (men cơ CK), chức năng thận và được đánh giá y khoa.",
                red_flags=red_flags,
            )

        # 2. Delayed Onset Muscle Soreness (DOMS) / Exercise soreness
        exercise_pattern = bool(re.search(r"\b(?:tap gym|sau tap|moi co|cang co|chay bo|nang ta|tap luyen|dau co)\b", norm))

        if exercise_pattern:
            return DomainAssessment(
                risk_level="ROUTINE",
                subtype="exercise_soreness_doms",
                rationale=(
                    "Cảm giác đau mỏi cơ sau tập luyện hoặc vận động cơ bắp là phản ứng sinh lý lành tính thường gặp "
                    "(đau cơ khởi phát muộn - DOMS) do vi tổn thương sợi cơ trong quá trình thích nghi vận động."
                ),
                suggested_action=(
                    "Nghỉ ngơi, bổ sung đủ nước và điện giải, dinh dưỡng giàu đạm; có thể chườm ấm hoặc tắm nước ấm để thư giãn cơ. "
                    "Không lạm dụng thuốc giảm đau khi chưa cần thiết. Đi khám nếu đau kéo dài trên 7 ngày hoặc xuất hiện nước tiểu sẫm màu."
                ),
                red_flags=[],
            )

        return DomainAssessment(
            risk_level="ROUTINE",
            subtype="general_myalgia",
            rationale="Đau mỏi cơ thông thường, không kèm sưng nề khu trú hay dấu hiệu toàn thân bất thường.",
            suggested_action="Nghỉ ngơi, vận động nhẹ nhàng và theo dõi diễn tiến.",
            red_flags=[],
        )
