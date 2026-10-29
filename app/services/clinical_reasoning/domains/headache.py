"""Headache clinical reasoning domain."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.services.clinical_text import normalize_search_text
from app.services.clinical_reasoning.negation_engine import NegationEngine


@dataclass
class DomainAssessment:
    risk_level: str  # ROUTINE, URGENT, EMERGENCY
    subtype: str
    rationale: str
    suggested_action: str
    red_flags: list[str]


class HeadacheReasoner:
    """Distinguish common headache patterns from urgent neurologic warnings."""

    def __init__(self) -> None:
        self.negation_engine = NegationEngine()

    def _affirmed_regex(self, norm: str, pattern: str) -> bool:
        """Return True only for a locally affirmed match."""
        for match in re.finditer(pattern, norm):
            phrase = match.group(0).strip()
            if phrase and not self.negation_engine.detect(norm, phrase):
                return True
        return False

    def evaluate(self, text: str, clinical_context: Any) -> DomainAssessment:
        norm = normalize_search_text(text)
        positive = getattr(clinical_context, "positive_findings", {}) or {}
        red_flags: list[str] = []

        # 1. Thunderclap / worst-ever headache.
        # Ordinary high intensity ("đau đầu dữ dội", "rất đau") is important
        # but is not equivalent to thunderclap. Emergency classification here
        # requires either hyperacute onset language or a true maximal/worst-ever
        # formulation. Novelty alone ("chưa từng bị như vậy") is also not enough.
        has_headache = bool(positive.get("headache")) or self._affirmed_regex(
            norm, r"\b(?:dau dau|nhuc dau|con dau dau)\b"
        )
        sudden_onset = self._affirmed_regex(
            norm, r"\b(?:dot ngot|set danh|nhu set danh|bung phat|dau nhu bua bo)\b"
        )
        worst_ever = self._affirmed_regex(
            norm,
            r"\b(?:du doi nhat|dau nhat tu truoc toi gio|dau dau nang nhat tu truoc toi gio|con dau dau nang nhat)\b",
        )
        thunderclap_or_worst = has_headache and (sudden_onset or worst_ever)

        # 2. Focal neurological deficit. These words must be affirmed; a phrase
        # such as "không yếu tay, không nói ngọng" must never create a red flag.
        focal_neuro = self._affirmed_regex(
            norm,
            r"\b(?:meo mieng|lech mieng|noi ngong|yeu tay|yeu chan|yeu nua nguoi|mat thi luc|nhin mo dot ngot|co giat|hon me)\b",
        )

        # 3. Infection / meningismus. Fever may come from structured findings;
        # neck stiffness/confusion still require an affirmed local mention.
        fever_present = bool(positive.get("fever")) or self._affirmed_regex(norm, r"\bsot\b")
        meningismus = fever_present and self._affirmed_regex(
            norm, r"\b(?:cung co|co cung|lu lan)\b"
        )

        # 4. Recent head trauma. Trauma alone is not automatically an emergency,
        # but trauma plus loss of consciousness, repeated vomiting, seizure or a
        # focal deficit is time-sensitive.
        head_trauma = self._affirmed_regex(
            norm,
            r"\b(?:va dau|dap dau|nga dap dau|chan thuong dau|bi danh vao dau|va dap dau)\b",
        )
        trauma_emergency = head_trauma and self._affirmed_regex(
            norm,
            r"\b(?:ngat|bat tinh|mat y thuc|non nhieu|non lien tuc|non lap lai|co giat|lu lan|kho danh thuc)\b",
        )

        if thunderclap_or_worst:
            red_flags.append("thunderclap_headache")
        if focal_neuro:
            red_flags.append("focal_neurological_deficit")
        if meningismus:
            red_flags.append("meningeal_signs")
        if trauma_emergency:
            red_flags.append("head_trauma_with_neurological_warning")

        if red_flags:
            return DomainAssessment(
                risk_level="EMERGENCY",
                subtype="neurological_emergency",
                rationale=(
                    "Đau đầu khởi phát đột ngột hoặc ở mức nặng nhất từng trải qua, dấu hiệu thần kinh khu trú, sốt kèm cứng cổ/lú lẫn, "
                    "hoặc chấn thương đầu kèm mất ý thức, nôn lặp lại hay co giật là các dấu hiệu cần đánh giá cấp cứu."
                ),
                suggested_action="Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức; không tự lái xe.",
                red_flags=red_flags,
            )

        # 5. Severe headache or headache after trauma without hard emergency
        # features still deserves prompt assessment rather than being silently
        # downgraded to routine self-care.
        severe_non_thunderclap = self._affirmed_regex(
            norm,
            r"\b(?:rat du doi|dau dau du doi|dau dau rat nhieu|dau dau nang|dau du doi|dau rat nhieu)\b",
        )
        if head_trauma or severe_non_thunderclap:
            urgent_flags = []
            if head_trauma:
                urgent_flags.append("recent_head_trauma")
            if severe_non_thunderclap:
                urgent_flags.append("severe_headache")
            return DomainAssessment(
                risk_level="URGENT",
                subtype="headache_needs_prompt_assessment",
                rationale=(
                    "Đau đầu dữ dội hoặc xuất hiện sau va đập/chấn thương đầu cần được đánh giá sớm. Trong mô tả hiện tại chưa có đủ dữ kiện để khẳng định hay loại trừ nguyên nhân thần kinh nghiêm trọng."
                ),
                suggested_action=(
                    "Sắp xếp khám trong ngày. Nếu xuất hiện lơ mơ, nôn lặp lại, yếu liệt, nói khó, co giật, ngất hoặc đau tăng nhanh thì gọi 115 ngay."
                ),
                red_flags=urgent_flags,
            )

        # 6. Common / benign lifestyle patterns.
        sleep_or_screen = self._affirmed_regex(
            norm,
            r"\b(?:thuc khuya|thieu ngu|nhin man hinh|man hinh ca ngay|moi mat|cang thang|stress)\b",
        )

        if sleep_or_screen:
            return DomainAssessment(
                risk_level="ROUTINE",
                subtype="tension_or_lifestyle_headache",
                rationale=(
                    "Đau đầu sau thức khuya, thiếu ngủ hoặc làm việc với màn hình kéo dài có thể phù hợp với căng đầu-cổ hoặc mỏi thị giác. "
                    "Các dấu hiệu thần kinh cảnh báo không được ghi nhận trong mô tả hiện tại, nhưng điều đó không thay thế đánh giá trực tiếp nếu triệu chứng thay đổi."
                ),
                suggested_action="Nghỉ ngơi, ngủ đủ giấc, giảm thời gian màn hình, uống đủ nước và theo dõi thêm.",
                red_flags=[],
            )

        return DomainAssessment(
            risk_level="ROUTINE",
            subtype="common_headache",
            rationale=(
                "Mô tả hiện tại chưa ghi nhận khởi phát sét đánh, dấu hiệu thần kinh khu trú, sốt kèm cứng cổ/lú lẫn hay chấn thương đầu. "
                "Chỉ từ tin nhắn vẫn chưa đủ để xác định nguyên nhân cụ thể."
            ),
            suggested_action="Nghỉ ngơi trong không gian yên tĩnh, uống đủ nước và theo dõi diễn tiến.",
            red_flags=[],
        )
