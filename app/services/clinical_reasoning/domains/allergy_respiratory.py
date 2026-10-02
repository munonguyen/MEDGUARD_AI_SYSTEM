"""Allergy and respiratory clinical reasoning domain."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.services.clinical_text import normalize_search_text
from app.services.clinical_reasoning.domains.headache import DomainAssessment


class AllergyRespiratoryReasoner:
    """Evaluates allergic reactions, toxic inhalations and respiratory distress."""

    def evaluate(self, text: str, clinical_context: Any) -> DomainAssessment:
        norm = normalize_search_text(text)
        red_flags: list[str] = []

        # 1. Anaphylaxis / Angioedema red flags
        angioedema = bool(re.search(r"\b(?:sung moi|sung luoi|sung mat|sung hong|phu moi|phu mat)\b", norm))
        airway_tightness = bool(re.search(r"\b(?:nghen co hong|nghet hong|kho tho|tho rit|tho gap|moi hoi tim)\b", norm))
        allergy_context = bool(re.search(r"\b(?:uong thuoc|sau khi uong|me day|phat ban|ong dot|di ung)\b", norm))

        if (angioedema or airway_tightness) and (allergy_context or angioedema):
            if angioedema:
                red_flags.append("angioedema_facial_swelling")
            if airway_tightness:
                red_flags.append("airway_compromise_dyspnea")

            return DomainAssessment(
                risk_level="EMERGENCY",
                subtype="anaphylaxis_airway_emergency",
                rationale=(
                    "Dị ứng tiến triển nhanh kèm sưng nề vùng môi/lưỡi/mặt hoặc có cảm giác nghẹn họng, khó thở "
                    "là biểu hiện của phản ứng phản vệ cấp tính (anaphylaxis) có nguy cơ tắc nghẽn đường thở đe dọa tính mạng."
                ),
                suggested_action="Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức để được tiêm bắp Adrenaline và can thiệp hồi sức.",
                red_flags=red_flags,
            )

        # 2. Toxic chemical inhalation
        chemical_inhalation = bool(re.search(r"\b(?:hoa chat|tay rua|mui clo|khi doc|phong kin)\b", norm))
        inhalation_symptoms = bool(re.search(r"\b(?:kho tho|tuc nguc|ho nhieu|rat hong|chong mat)\b", norm))

        if chemical_inhalation and inhalation_symptoms:
            return DomainAssessment(
                risk_level="EMERGENCY",
                subtype="toxic_inhalation_respiratory_injury",
                rationale=(
                    "Hít phải hơi/khí hóa chất tẩy rửa trong không gian kín dẫn đến khó thở hoặc kích ứng đường hô hấp "
                    "có nguy cơ gây viêm đường thở cấp tính hoặc phù phổi nhiễm độc hóa chất."
                ),
                suggested_action="Di chuyển ngay ra nơi thoáng khí trong lành và gọi 115 hoặc đến cơ sở y tế cấp cứu ngay.",
                red_flags=["toxic_inhalation_dyspnea"],
            )

        # 3. Simple localized cutaneous allergy
        if allergy_context or "me day" in norm or "phat ban" in norm:
            return DomainAssessment(
                risk_level="ROUTINE",
                subtype="localized_cutaneous_allergy",
                rationale=(
                    "Phản ứng mày đay hoặc phát ban ngoài da đơn thuần, hiện tại không có dấu hiệu phù mặt môi hay khó thở."
                ),
                suggested_action=(
                    "Ngừng tiếp xúc ngay với dị nguyên nghi ngờ (thuốc mới, thức ăn lạ). "
                    "Nếu xuất hiện sưng môi, nghẹn họng, chóng mặt hoặc khó thở thì phải gọi cấp cứu ngay lập tức."
                ),
                red_flags=[],
            )

        return DomainAssessment(
            risk_level="ROUTINE",
            subtype="mild_respiratory_symptom",
            rationale="Triệu chứng hô hấp nhẹ không kèm co kéo lồng ngực, tím tái hay khó thở khi nghỉ.",
            suggested_action="Nghỉ ngơi, theo dõi sát nhịp thở và đi khám nếu tình trạng khó thở gia tăng.",
            red_flags=[],
        )
