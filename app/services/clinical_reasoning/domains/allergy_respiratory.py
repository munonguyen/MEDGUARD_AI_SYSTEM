"""Allergy and respiratory clinical reasoning domain."""

from __future__ import annotations

import re
from typing import Any

from app.services.clinical_text import normalize_search_text
from app.services.clinical_reasoning.domains.headache import DomainAssessment


class AllergyRespiratoryReasoner:
    """Evaluate allergic reactions, inhalation injuries and airway compromise.

    Present-vs-hypothetical symptom status is taken from the structured context
    whenever available so contingency questions do not become false active
    emergencies merely because they contain words such as "sưng môi" or
    "khó thở".
    """

    def evaluate(self, text: str, clinical_context: Any) -> DomainAssessment:
        norm = normalize_search_text(text)
        positive = getattr(clinical_context, "positive_findings", {}) or {}
        red_flags: list[str] = []

        angioedema = bool(positive.get("angioedema"))
        airway_tightness = bool(
            positive.get("throat_tightness") or positive.get("shortness_of_breath")
        )
        rash_present = bool(positive.get("rash"))
        allergy_context = bool(
            re.search(r"\b(?:uong thuoc|sau khi uong|ong dot|di ung)\b", norm)
        ) or rash_present

        if (angioedema or airway_tightness) and (allergy_context or angioedema):
            if angioedema:
                red_flags.append("angioedema_facial_swelling")
            if airway_tightness:
                red_flags.append("airway_compromise_dyspnea")

            return DomainAssessment(
                risk_level="EMERGENCY",
                subtype="anaphylaxis_airway_emergency",
                rationale=(
                    "Dị ứng đang diễn ra kèm sưng môi/lưỡi/mặt hoặc nghẹn họng, khó thở là dấu hiệu cảnh báo phản vệ/phù đường thở cần xử trí khẩn cấp."
                ),
                suggested_action=(
                    "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức. Nếu người bệnh đã được bác sĩ kê bút adrenaline tự tiêm cho phản vệ trước đây, sử dụng theo kế hoạch cấp cứu cá nhân đã được hướng dẫn; không trì hoãn việc gọi cấp cứu."
                ),
                red_flags=red_flags,
            )

        # Toxic chemical inhalation must rely on a current respiratory finding,
        # not merely a hypothetical phrase embedded in the question.
        chemical_inhalation = bool(
            re.search(r"\b(?:hoa chat|tay rua|mui clo|khi doc|phong kin)\b", norm)
        )
        inhalation_symptoms = bool(
            positive.get("shortness_of_breath")
            or positive.get("chest_pain")
            or positive.get("dizziness")
            or re.search(r"\b(?:ho nhieu|rat hong)\b", norm)
        )

        if chemical_inhalation and inhalation_symptoms:
            return DomainAssessment(
                risk_level="EMERGENCY",
                subtype="toxic_inhalation_respiratory_injury",
                rationale=(
                    "Hít phải hơi/khí hóa chất trong không gian kín kèm khó thở, tức ngực, chóng mặt hoặc kích ứng hô hấp rõ có thể là tổn thương hô hấp cấp do hóa chất."
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
                    "Hiện dữ kiện phù hợp hơn với phản ứng da khu trú/mày đay và chưa có dấu hiệu đường thở đang xảy ra trong các finding hiện tại."
                ),
                suggested_action=(
                    "Ngừng tiếp xúc với tác nhân nghi ngờ nếu an toàn. Nếu thực sự xuất hiện sưng môi/lưỡi, nghẹn họng, khó thở, choáng hoặc ngất thì gọi cấp cứu ngay."
                ),
                red_flags=[],
            )

        return DomainAssessment(
            risk_level="ROUTINE",
            subtype="mild_respiratory_symptom",
            rationale="Chưa ghi nhận trong structured findings các dấu hiệu đường thở nguy kịch đang xảy ra.",
            suggested_action="Theo dõi sát; đi khám nếu triệu chứng hô hấp tăng, kéo dài hoặc ảnh hưởng hoạt động thường ngày.",
            red_flags=[],
        )
