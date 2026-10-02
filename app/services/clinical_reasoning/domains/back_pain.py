"""Back pain clinical reasoning domain."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.services.clinical_text import normalize_search_text
from app.services.clinical_reasoning.domains.headache import DomainAssessment
from app.services.clinical_reasoning.negation_engine import NegationEngine


class BackPainReasoner:
    """Evaluates back pain presentations, safeguarding against false Cauda Equina emergencies."""

    def __init__(self) -> None:
        self.negation_engine = NegationEngine()

    def evaluate(self, text: str, clinical_context: Any) -> DomainAssessment:
        norm = normalize_search_text(text)
        red_flags: list[str] = []

        # 1. Check for spinal emergency red flags with strict negation verification
        raw_leg_weakness = bool(re.search(r"\b(?:yeu chan|chan yeu|kho nhac ban chan|sup ban chan|foot drop|liet chan|yeu hai chan)\b", norm))
        leg_weakness = raw_leg_weakness and not self.negation_engine.detect(norm, "yeu chan") and not self.negation_engine.detect(norm, "liet chan") and not self.negation_engine.detect(norm, "yeu hai chan")

        raw_saddle = bool(re.search(r"\b(?:te vung yen ngua|te quanh hau mon|te quanh mong|te quanh sinh duc)\b", norm))
        saddle = raw_saddle and not self.negation_engine.detect(norm, "te")

        raw_incontinence = bool(re.search(r"\b(?:kho kiem soat tieu|tieu khong tu chu|bi tieu|khong tieu duoc|bi dai tien|mat kiem soat tieu tien)\b", norm))
        incontinence = raw_incontinence and not self.negation_engine.detect(norm, "tieu")

        if leg_weakness:
            red_flags.append("new_leg_weakness")
        if saddle:
            red_flags.append("saddle_sensory_change")
        if incontinence:
            red_flags.append("bladder_bowel_incontinence")

        # Spinal emergency / Cauda Equina syndrome criteria
        if red_flags:
            return DomainAssessment(
                risk_level="EMERGENCY",
                subtype="spinal_neurological_emergency",
                rationale=(
                    "Đau lưng đi kèm yếu hai chân, mất cảm giác vùng yên ngựa hoặc rối loạn tiểu tiện/đại tiện "
                    "là dấu hiệu cảnh báo chèn ép rễ thần kinh tủy sống nghiêm trọng (hội chứng chùm đuôi ngựa) cần giải áp phẫu thuật cấp cứu."
                ),
                suggested_action="Gọi 115 hoặc đến khoa Cấp cứu bệnh viện có chuyên khoa cột sống/thần kinh ngay lập tức.",
                red_flags=red_flags,
            )

        # 2. Postural / Mechanical back pain
        posture_pattern = bool(re.search(r"\b(?:ngoi may tinh|ngoi lau|ngoi ca ngay|moi lung|thay doi tu the|di lai thi giam|di lai thi de chiu)\b", norm))

        if posture_pattern:
            return DomainAssessment(
                risk_level="ROUTINE",
                subtype="mechanical_postural_back_pain",
                rationale=(
                    "Đau mỏi lưng liên quan đến tư thế ngồi làm việc kéo dài và giảm khi đi lại, không kèm theo tê yếu chân "
                    "hay rối loạn tiểu tiện, là biểu hiện điển hình của quá tải cơ cạnh cột sống cơ học lành tính."
                ),
                suggested_action=(
                    "Điều chỉnh tư thế ngồi công thái học, đứng dậy vận động nhẹ nhàng sau mỗi 45–60 phút, "
                    "kết hợp các bài tập kéo giãn cơ lưng nhẹ nhàng. Theo dõi và đi khám nếu đau lan xuống chân hoặc tê yếu."
                ),
                red_flags=[],
            )

        return DomainAssessment(
            risk_level="ROUTINE",
            subtype="common_mechanical_back_pain",
            rationale="Đau lưng cơ học thông thường không có dấu hiệu chèn ép thần kinh hay tổn thương cấp tính.",
            suggested_action="Nghỉ ngơi, tránh cúi gập người mang vác nặng và theo dõi triệu chứng.",
            red_flags=[],
        )
