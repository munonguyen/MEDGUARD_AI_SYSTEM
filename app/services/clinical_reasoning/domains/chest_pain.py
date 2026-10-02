"""Chest pain clinical reasoning domain."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.services.clinical_text import normalize_search_text
from app.services.clinical_reasoning.domains.headache import DomainAssessment


class ChestPainReasoner:
    """Evaluates chest symptoms to accurately differentiate musculoskeletal pain from cardiac emergencies."""

    def evaluate(self, text: str, clinical_context: Any) -> DomainAssessment:
        norm = normalize_search_text(text)
        red_flags: list[str] = []

        # 0. Check if chest is just a rash/skin location
        is_skin_only = bool(re.search(r"\b(?:ban lan|me day|noi man|phat ban|vet dot).*(?:nguc|thanh nguc)\b", norm))
        if is_skin_only and not any(w in norm for w in ("tuc nguc", "nang nguc", "dau nguc", "kho tho")):
            return DomainAssessment(
                risk_level="ROUTINE",
                subtype="dermatological_chest_involvement",
                rationale="Biểu hiện phát ban hoặc tổn thương ngoài da vùng ngực, không có dấu hiệu đau tức ngực sâu.",
                suggested_action="Theo dõi diễn tiến ban da và tránh gãi xước.",
                red_flags=[],
            )

        # 1. Cardiac Red Flags
        has_pressure = bool(re.search(r"\b(?:tuc nguc|nang nguc|de ep|ep nguc|bop nghet|dau nguc)\b", norm))
        has_dyspnea = bool(re.search(r"\b(?:kho tho|hut hoi|tho gap)\b", norm))
        has_sweating = bool(re.search(r"\b(?:va mo hoi|toat mo hoi|mo hoi lanh)\b", norm))
        has_radiation = bool(re.search(r"\b(?:lan.*tay trai|lan.*canh tay|lan.*ham|lan.*lung|lan.*vai)\b", norm))
        has_syncope = bool(re.search(r"\b(?:choang|gan ngat|ngat xiu|xay sam)\b", norm))

        cardiac_cluster = has_pressure and (has_dyspnea or has_sweating or has_radiation or has_syncope)

        if cardiac_cluster:
            if has_dyspnea:
                red_flags.append("dyspnea")
            if has_sweating:
                red_flags.append("diaphoresis")
            if has_radiation:
                red_flags.append("radiation")
            if has_syncope:
                red_flags.append("syncope_or_presyncope")

            return DomainAssessment(
                risk_level="EMERGENCY",
                subtype="cardiac_emergency_warning",
                rationale=(
                    "Cảm giác nặng hoặc đau tức ngực kèm theo khó thở, vã mồ hôi hoặc đau lan ra tay/hàm "
                    "là các dấu hiệu cảnh báo bệnh cảnh tim mạch cấp tính cần được can thiệp y tế khẩn cấp."
                ),
                suggested_action="Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức; không tự lái xe và không trì hoãn.",
                red_flags=red_flags,
            )

        # 2. Musculoskeletal / Chest wall features
        post_exercise = bool(re.search(r"\b(?:chong day|tap gym|nang ta|tap nguc|tap luyen|sau van dong)\b", norm))
        palpation_pain = bool(re.search(r"\b(?:an vao.*dau|dau hon khi an|dau tang khi an|dau khi an|dau khi van dong|co co.*dau)\b", norm))

        if post_exercise or palpation_pain:
            return DomainAssessment(
                risk_level="ROUTINE",
                subtype="musculoskeletal_chest_wall",
                rationale=(
                    "Đau ngực xuất hiện sau khi vận động, tập thể thao (chống đẩy/tập gym) và tăng lên khi ấn tại chỗ "
                    "thường phù hợp với căng cơ thành ngực hoặc viêm sụn sườn cơ học, ít nghĩ đến nguyên nhân tim mạch nếu không kèm khó thở hay đau lan."
                ),
                suggested_action=(
                    "Nghỉ ngơi, tránh các động tác mang vác hay ép cơ ngực; có thể chườm mát/ấm nhẹ. "
                    "Nếu xuất hiện cảm giác đè nặng ngực, khó thở, đau lan hoặc vã mồ hôi thì cần đi cấp cứu ngay."
                ),
                red_flags=[],
            )

        # 3. Default chest discomfort
        return DomainAssessment(
            risk_level="ROUTINE",
            subtype="unspecified_chest_discomfort",
            rationale="Cảm giác khó chịu vùng ngực mức độ nhẹ, cần làm rõ thêm tính chất cơn đau và mối liên hệ với gắng sức.",
            suggested_action="Nghỉ ngơi và theo dõi sát. Đi khám chuyên khoa sớm hoặc gọi cấp cứu nếu triệu chứng nặng lên hay kèm khó thở.",
            red_flags=[],
        )
