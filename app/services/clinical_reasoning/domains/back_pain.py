"""Back pain clinical reasoning domain."""

from __future__ import annotations

import re
from typing import Any

from app.services.clinical_text import normalize_search_text
from app.services.clinical_reasoning.domains.headache import DomainAssessment
from app.services.clinical_reasoning.negation_engine import NegationEngine


class BackPainReasoner:
    """Evaluate back pain without confusing unknown findings with negatives."""

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

        # 1. Spinal-neurologic warning features. Use structured findings where
        # available and whole-phrase checks for urinary retention. In Vietnamese,
        # "không tiểu được" is itself a positive symptom (urinary retention),
        # whereas "không bí tiểu" is a true negation; these must not be conflated.
        leg_weakness = bool(positive.get("leg_weakness")) or self._affirmed_regex(
            norm,
            r"\b(?:chan yeu|kho nhac ban chan|sup ban chan|foot drop|yeu hai chan|liet chan)\b",
        )
        saddle = self._affirmed_regex(
            norm,
            r"\b(?:te vung yen ngua|te quanh hau mon|te quanh mong|te quanh sinh duc|mat cam giac quanh hau mon|mat cam giac vung yen ngua)\b",
        )

        unable_to_void = bool(
            re.search(
                r"\b(?:khong tieu duoc|buon tieu.*khong tieu duoc|cang bang quang.*khong tieu duoc)\b",
                norm,
            )
        )
        retention_named = self._affirmed_regex(norm, r"\b(?:bi tieu tien|bi tieu)\b")
        urinary_retention = unable_to_void or retention_named

        bladder_bowel_loss = bool(positive.get("incontinence")) or self._affirmed_regex(
            norm,
            r"\b(?:tieu khong tu chu|mat kiem soat tieu tien|dai tien khong tu chu|mat kiem soat dai tien)\b",
        )
        bladder_bowel_dysfunction = urinary_retention or bladder_bowel_loss

        if leg_weakness:
            red_flags.append("new_leg_weakness")
        if saddle:
            red_flags.append("saddle_sensory_change")
        if bladder_bowel_dysfunction:
            red_flags.append("new_bladder_bowel_dysfunction")

        if red_flags:
            return DomainAssessment(
                risk_level="EMERGENCY",
                subtype="spinal_neurological_emergency",
                rationale=(
                    "Đau lưng kèm yếu chân mới xuất hiện, thay đổi cảm giác vùng yên ngựa hoặc rối loạn tiểu tiện/đại tiện mới xuất hiện có thể gợi ý chèn ép thần kinh nghiêm trọng. "
                    "Không thể xác định hội chứng chùm đuôi ngựa chỉ từ tin nhắn, nhưng các dấu hiệu này cần được đánh giá cấp cứu để không bỏ sót tình trạng cần can thiệp sớm."
                ),
                suggested_action=(
                    "Đến khoa Cấp cứu ngay hoặc gọi 115 nếu không thể di chuyển an toàn, đặc biệt khi yếu chân tăng, mất cảm giác vùng sinh dục-hậu môn, bí tiểu hoặc mất kiểm soát tiểu/đại tiện."
                ),
                red_flags=red_flags,
            )

        # 2. Postural / mechanical pattern. This can support a benign mechanism
        # but must not invent negative neurologic findings the user never gave.
        posture_pattern = self._affirmed_regex(
            norm,
            r"\b(?:ngoi may tinh|ngoi lau|ngoi ca ngay|thay doi tu the|di lai thi giam|di lai thi de chiu)\b",
        )

        if posture_pattern:
            return DomainAssessment(
                risk_level="ROUTINE",
                subtype="mechanical_postural_back_pain",
                rationale=(
                    "Mối liên hệ với ngồi lâu/làm việc máy tính hoặc cải thiện khi thay đổi tư thế có thể phù hợp với đau lưng cơ học do quá tải tư thế. "
                    "Mô tả hiện tại chưa ghi nhận red flag thần kinh, nhưng các dấu hiệu chưa được hỏi tới vẫn phải xem là chưa biết chứ không phải âm tính."
                ),
                suggested_action=(
                    "Điều chỉnh tư thế, đổi vị trí thường xuyên, đứng dậy vận động nhẹ sau mỗi 45–60 phút và tránh bất động kéo dài. "
                    "Đi khám nếu đau kéo dài/tăng dần hoặc lan xuống chân; đi cấp cứu nếu xuất hiện yếu chân mới, tê vùng sinh dục-hậu môn, bí tiểu hoặc mất kiểm soát tiểu/đại tiện."
                ),
                red_flags=[],
            )

        return DomainAssessment(
            risk_level="ROUTINE",
            subtype="common_mechanical_back_pain",
            rationale=(
                "Từ thông tin hiện có chưa ghi nhận dấu hiệu cấp cứu cột sống, nhưng cũng chưa đủ dữ kiện để xác định nguyên nhân hoặc coi các dấu hiệu chưa đề cập là âm tính."
            ),
            suggested_action=(
                "Duy trì hoạt động nhẹ trong ngưỡng chịu được, tránh mang vác nặng tạm thời và theo dõi. Đi khám nếu đau kéo dài, tăng dần hoặc kèm đau lan/tê yếu; đi cấp cứu nếu xuất hiện yếu chân mới, tê vùng yên ngựa, bí tiểu hoặc mất kiểm soát tiểu/đại tiện."
            ),
            red_flags=[],
        )
