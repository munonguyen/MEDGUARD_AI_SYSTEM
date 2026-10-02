"""Chest pain clinical reasoning domain."""

from __future__ import annotations

import re
from typing import Any

from app.services.clinical_text import normalize_search_text
from app.services.clinical_reasoning.domains.headache import DomainAssessment


class ChestPainReasoner:
    """Differentiate chest-wall pain from exertional/cardiac warning patterns.

    The reasoner is intentionally conservative about *exertional* chest pain:
    exercise is not automatically reassuring. Strength-training soreness or
    pain reproducible by palpation can support a chest-wall pattern, whereas
    pressure/heaviness brought on by walking/running/stairs needs prompt
    clinical assessment even if classic emergency accompaniments are absent.
    """

    def evaluate(self, text: str, clinical_context: Any) -> DomainAssessment:
        norm = normalize_search_text(text)
        red_flags: list[str] = []

        # 0. Check if chest is just a rash/skin location.
        is_skin_only = bool(
            re.search(r"\b(?:ban lan|me day|noi man|phat ban|vet dot).*(?:nguc|thanh nguc)\b", norm)
        )
        if is_skin_only and not any(w in norm for w in ("tuc nguc", "nang nguc", "dau nguc", "kho tho")):
            return DomainAssessment(
                risk_level="ROUTINE",
                subtype="dermatological_chest_involvement",
                rationale="Biểu hiện phát ban hoặc tổn thương ngoài da vùng ngực, không có dấu hiệu đau tức ngực sâu.",
                suggested_action="Theo dõi diễn tiến ban da và tránh gãi xước.",
                red_flags=[],
            )

        # 1. Cardiac / cardiopulmonary red-flag cluster.
        has_pressure = bool(
            re.search(r"\b(?:tuc nguc|nang nguc|de ep|ep nguc|bop nghet|dau nguc)\b", norm)
        )
        has_dyspnea = bool(re.search(r"\b(?:kho tho|hut hoi|tho gap)\b", norm))
        has_sweating = bool(re.search(r"\b(?:va mo hoi|toat mo hoi|mo hoi lanh)\b", norm))
        has_radiation = bool(
            re.search(r"\b(?:lan.*tay trai|lan.*canh tay|lan.*ham|lan.*lung|lan.*vai)\b", norm)
        )
        has_syncope = bool(re.search(r"\b(?:choang|gan ngat|ngat xiu|xay sam)\b", norm))

        cardiac_cluster = has_pressure and (
            has_dyspnea or has_sweating or has_radiation or has_syncope
        )

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
                    "Cảm giác nặng hoặc đau tức ngực kèm theo khó thở, vã mồ hôi, đau lan hoặc gần ngất "
                    "là tổ hợp cảnh báo bệnh cảnh tim mạch/cardiopulmonary cấp cần được đánh giá khẩn cấp."
                ),
                suggested_action="Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức; không tự lái xe và không trì hoãn.",
                red_flags=red_flags,
            )

        # 2. Separate exertional ischemic warning from strength-training chest-wall soreness.
        exertional_pattern = bool(
            re.search(
                r"\b(?:khi di bo(?: nhanh)?|khi chay(?: bo)?|khi leo cau thang|khi gang suc|khi van dong|dang van dong|di bo nhanh thi|chay thi)\b",
                norm,
            )
        )
        palpation_pain = bool(
            re.search(
                r"\b(?:an vao.*dau|dau hon khi an|dau tang khi an|dau khi an|an.*nguc.*dau|co co.*dau)\b",
                norm,
            )
        )
        strength_training_trigger = bool(
            re.search(r"\b(?:chong day|tap gym|nang ta|tap nguc|tap ta)\b", norm)
        )

        if has_pressure and exertional_pattern and not palpation_pain:
            return DomainAssessment(
                risk_level="URGENT",
                subtype="exertional_chest_pain_needs_prompt_assessment",
                rationale=(
                    "Đau/nặng ngực xuất hiện khi đi bộ nhanh, chạy, leo cầu thang hoặc gắng sức không nên được quy cho đau cơ chỉ vì có yếu tố vận động. "
                    "Kiểu khởi phát theo gắng sức cần được đánh giá sớm để loại trừ nguyên nhân tim-phổi."
                ),
                suggested_action=(
                    "Ngừng gắng sức và sắp xếp đánh giá y tế sớm trong ngày. Nếu đau kéo dài, tăng lên, xuất hiện khi nghỉ, hoặc kèm khó thở, vã mồ hôi, đau lan hay gần ngất thì gọi 115 ngay."
                ),
                red_flags=["exertional_chest_pain"],
            )

        # 3. Musculoskeletal / chest-wall pattern.
        if palpation_pain or strength_training_trigger:
            return DomainAssessment(
                risk_level="ROUTINE",
                subtype="musculoskeletal_chest_wall",
                rationale=(
                    "Đau ngực sau chống đẩy/tập tạ hoặc tăng rõ khi ấn tại chỗ phù hợp hơn với căng cơ thành ngực hoặc đau thành ngực do vận động. "
                    "Đây không phải là bằng chứng tuyệt đối loại trừ nguyên nhân tim-phổi, nên vẫn cần theo dõi dấu hiệu cảnh báo."
                ),
                suggested_action=(
                    "Tạm giảm bài tập ngực, nghỉ ngơi và có thể chườm mát/ấm nhẹ. Nếu xuất hiện cảm giác đè nặng ngực, khó thở, đau lan, vã mồ hôi hoặc gần ngất thì cần đi cấp cứu ngay."
                ),
                red_flags=[],
            )

        # 4. Default chest discomfort: do not diagnose from an isolated keyword.
        return DomainAssessment(
            risk_level="ROUTINE",
            subtype="unspecified_chest_discomfort",
            rationale=(
                "Chỉ từ mô tả đau/khó chịu vùng ngực hiện chưa đủ dữ kiện để xác định cơ chế. Cần làm rõ tính chất đau, thời điểm, mối liên hệ với gắng sức, hô hấp và các triệu chứng kèm theo."
            ),
            suggested_action=(
                "Nghỉ ngơi và theo dõi sát; đi khám sớm nếu triệu chứng tái diễn hoặc liên quan gắng sức. Gọi cấp cứu nếu đau tăng, kéo dài hoặc kèm khó thở, vã mồ hôi, đau lan hay ngất."
            ),
            red_flags=[],
        )
