"""Allergy and respiratory clinical reasoning domain."""

from __future__ import annotations

import re
from typing import Any

from app.services.clinical_text import normalize_search_text
from app.services.clinical_reasoning.domains.headache import DomainAssessment
from app.services.clinical_reasoning.negation_engine import NegationEngine


class AllergyRespiratoryReasoner:
    """Evaluate allergic reactions, inhalation injuries and airway compromise.

    Present-vs-hypothetical symptom status is taken from structured context.
    Exposure/allergy context must also be affirmed; negated mentions such as
    "không tiếp xúc hóa chất" must never create a toxic-inhalation emergency.
    """

    def __init__(self) -> None:
        self.negation_engine = NegationEngine()

    def _affirmed_regex(self, norm: str, pattern: str) -> bool:
        for match in re.finditer(pattern, norm):
            if not self.negation_engine.is_negated_at(norm, match.start()):
                return True
        return False

    def evaluate(self, text: str, clinical_context: Any) -> DomainAssessment:
        norm = normalize_search_text(text)
        positive = getattr(clinical_context, "positive_findings", {}) or {}
        triggers = set(getattr(clinical_context, "triggers", []) or [])
        red_flags: list[str] = []

        angioedema = bool(positive.get("angioedema"))
        airway_tightness = bool(
            positive.get("throat_tightness") or positive.get("shortness_of_breath")
        )
        rash_present = bool(positive.get("rash"))
        allergy_context = (
            rash_present
            or "medication_ingestion" in triggers
            or self._affirmed_regex(norm, r"\b(?:ong dot|di ung)\b")
        )

        if (angioedema or airway_tightness) and (allergy_context or angioedema):
            if angioedema:
                red_flags.append("angioedema_facial_swelling")
            if airway_tightness:
                red_flags.append("airway_compromise_dyspnea")

            return DomainAssessment(
                risk_level="EMERGENCY",
                subtype="anaphylaxis_airway_emergency",
                rationale=(
                    "Phản ứng dị ứng/phơi nhiễm đang được mô tả kèm sưng môi-lưỡi-mặt, nghẹn họng hoặc khó thở là tổ hợp cảnh báo phản vệ/phù đường thở cần xử trí khẩn cấp. "
                    "Không thể xác nhận chẩn đoán chỉ từ tin nhắn."
                ),
                suggested_action=(
                    "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức. Nếu người bệnh đã được bác sĩ kê bút adrenaline tự tiêm cho phản vệ trước đây, sử dụng theo kế hoạch cấp cứu cá nhân đã được hướng dẫn; không trì hoãn việc gọi cấp cứu."
                ),
                red_flags=red_flags,
            )

        chemical_inhalation = "chemical_exposure" in triggers
        inhalation_symptoms = bool(
            positive.get("shortness_of_breath")
            or positive.get("chest_pain")
            or positive.get("dizziness")
            or self._affirmed_regex(norm, r"\b(?:ho nhieu|rat hong)\b")
        )

        if chemical_inhalation and inhalation_symptoms:
            return DomainAssessment(
                risk_level="EMERGENCY",
                subtype="toxic_inhalation_respiratory_injury",
                rationale=(
                    "Phơi nhiễm hơi/khí hóa chất được xác nhận kèm khó thở, tức ngực, chóng mặt hoặc kích ứng hô hấp rõ có thể gây tổn thương hô hấp cấp và cần đánh giá khẩn."
                ),
                suggested_action=(
                    "Rời khỏi nguồn phơi nhiễm và ra nơi thoáng khí nếu có thể làm vậy an toàn; gọi 115 hoặc đến cơ sở cấp cứu nếu còn khó thở, tức ngực, chóng mặt nhiều hoặc triệu chứng tăng."
                ),
                red_flags=["toxic_inhalation_dyspnea"],
            )

        if allergy_context or rash_present:
            return DomainAssessment(
                risk_level="ROUTINE",
                subtype="localized_cutaneous_allergy",
                rationale=(
                    "Dữ kiện hiện tại phù hợp hơn với phản ứng da/dị ứng chưa có dấu hiệu đường thở đang được xác nhận. Các triệu chứng chưa được hỏi tới vẫn là chưa biết, không phải âm tính."
                ),
                suggested_action=(
                    "Ngừng tiếp xúc với tác nhân nghi ngờ nếu an toàn. Nếu thực sự xuất hiện sưng môi/lưỡi, nghẹn họng, khó thở, choáng hoặc ngất thì gọi cấp cứu ngay."
                ),
                red_flags=[],
            )

        return DomainAssessment(
            risk_level="ROUTINE",
            subtype="mild_respiratory_symptom",
            rationale=(
                "Structured findings hiện chưa cho thấy tổ hợp dị ứng hoặc phơi nhiễm hóa chất kèm dấu hiệu đường thở nguy kịch. Chỉ từ tin nhắn chưa đủ để xác định nguyên nhân khó chịu hô hấp."
            ),
            suggested_action="Theo dõi sát; đi khám nếu triệu chứng hô hấp tăng, kéo dài hoặc ảnh hưởng hoạt động thường ngày.",
            red_flags=[],
        )
