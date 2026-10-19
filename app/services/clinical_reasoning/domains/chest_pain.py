"""Chest pain clinical reasoning domain."""

from __future__ import annotations

import re
from typing import Any

from app.services.clinical_text import normalize_search_text
from app.services.clinical_reasoning.domains.headache import DomainAssessment
from app.services.clinical_reasoning.negation_engine import NegationEngine


class ChestPainReasoner:
    """Differentiate chest-wall pain from exertional/cardiac warning patterns.

    The reasoner is intentionally conservative about *exertional* chest pain:
    exercise is not automatically reassuring. Strength-training soreness or
    pain reproducible by palpation can support a chest-wall pattern, whereas
    pressure/heaviness brought on by walking/running/stairs needs prompt
    clinical assessment even if classic emergency accompaniments are absent.

    V28.2 safety rule: red-flag words are never treated as present merely
    because their text occurs in the utterance. Structured positive/negative
    findings and local negation scope take precedence.
    """

    def __init__(self) -> None:
        self.negation_engine = NegationEngine()

    def _affirmed_regex(self, norm: str, pattern: str) -> bool:
        """Return True only when a regex match is present and not locally negated."""
        for match in re.finditer(pattern, norm):
            phrase = match.group(0).strip()
            if phrase and not self.negation_engine.detect(norm, phrase):
                return True
        return False

    def evaluate(self, text: str, clinical_context: Any) -> DomainAssessment:
        norm = normalize_search_text(text)
        positive = getattr(clinical_context, "positive_findings", {}) or {}
        negative = getattr(clinical_context, "negative_findings", {}) or {}
        red_flags: list[str] = []

        # 0. Check if chest is just a rash/skin location.
        is_skin_only = bool(
            re.search(r"\b(?:ban lan|me day|noi man|phat ban|vet dot).*(?:nguc|thanh nguc)\b", norm)
        )
        if is_skin_only and not positive.get("chest_pain") and not positive.get("shortness_of_breath"):
            return DomainAssessment(
                risk_level="ROUTINE",
                subtype="dermatological_chest_involvement",
                rationale="Biểu hiện được mô tả chủ yếu ở da vùng ngực; chưa có đau tức ngực sâu hoặc khó thở được xác nhận trong structured findings.",
                suggested_action="Theo dõi diễn tiến ban da và tránh gãi xước.",
                red_flags=[],
            )

        # 1. Cardiac / cardiopulmonary red-flag cluster. Prefer structured
        # findings so "không khó thở" cannot become positive evidence.
        has_pressure = bool(positive.get("chest_pain"))
        if not positive and not negative:
            has_pressure = self._affirmed_regex(
                norm, r"\b(?:tuc nguc|nang nguc|de ep|ep nguc|bop nghet|dau nguc)\b"
            )

        has_dyspnea = bool(positive.get("shortness_of_breath"))
        has_sweating = bool(positive.get("sweating"))
        has_radiation = bool(positive.get("radiation"))
        has_syncope = self._affirmed_regex(
            norm, r"\b(?:choang|gan ngat|ngat xiu|xay sam|xay xam)\b"
        )

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
        exertional_pattern = self._affirmed_regex(
            norm,
            r"\b(?:khi di bo(?: nhanh)?|khi chay(?: bo)?|khi leo cau thang|khi gang suc|khi van dong|dang van dong|di bo nhanh thi|chay thi)\b",
        )
        palpation_pain = self._affirmed_regex(
            norm,
            r"\b(?:an vao.*dau|dau hon khi an|dau tang khi an|dau khi an|an.*nguc.*dau|co co.*dau)\b",
        )
        strength_training_trigger = self._affirmed_regex(
            norm, r"\b(?:chong day|tap gym|nang ta|tap nguc|tap ta)\b"
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
