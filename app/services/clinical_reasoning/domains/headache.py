"""Headache clinical reasoning domain."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.services.clinical_text import normalize_search_text


@dataclass
class DomainAssessment:
    risk_level: str  # ROUTINE, URGENT, EMERGENCY
    subtype: str
    rationale: str
    suggested_action: str
    red_flags: list[str]


class HeadacheReasoner:
    """Distinguish common headache patterns from urgent neurologic warnings."""

    def evaluate(self, text: str, clinical_context: Any) -> DomainAssessment:
        norm = normalize_search_text(text)
        red_flags: list[str] = []

        # 1. Thunderclap / sudden severe headache.
        sudden_severe = bool(
            re.search(
                r"\b(?:dot ngot|set danh|du doi nhat|chua tung bi|rat du doi)\b",
                norm,
            )
        ) and any(w in norm for w in ("dau dau", "dau", "con dau"))

        # 2. Focal neurological deficit.
        focal_neuro = bool(
            re.search(
                r"\b(?:meo mieng|lech mieng|noi ngong|yeu tay|yeu chan|yeu nua nguoi|mat thi luc|nhin mo dot ngot|co giat|hon me)\b",
                norm,
            )
        )

        # 3. Infection / meningismus.
        meningismus = "sot" in norm and any(w in norm for w in ("cung co", "co cung", "lu lan"))

        # 4. Recent head trauma. Trauma alone is not automatically an emergency,
        # but trauma plus loss of consciousness, repeated vomiting, seizure or a
        # focal deficit is time-sensitive.
        head_trauma = bool(
            re.search(
                r"\b(?:va dau|dap dau|nga dap dau|chan thuong dau|bi danh vao dau|va dap dau)\b",
                norm,
            )
        )
        trauma_emergency = head_trauma and bool(
            re.search(
                r"\b(?:ngat|bat tinh|mat y thuc|non nhieu|non lien tuc|non lap lai|co giat|lu lan|kho danh thuc)\b",
                norm,
            )
        )

        if sudden_severe:
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
                    "Đau đầu khởi phát đột ngột rất dữ dội, dấu hiệu thần kinh khu trú, sốt kèm cứng cổ/lú lẫn, "
                    "hoặc chấn thương đầu kèm mất ý thức, nôn lặp lại hay co giật là các dấu hiệu cần đánh giá cấp cứu."
                ),
                suggested_action="Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức; không tự lái xe.",
                red_flags=red_flags,
            )

        # 5. Severe headache or headache after trauma without hard emergency
        # features still deserves prompt assessment rather than being silently
        # downgraded to routine self-care.
        severe_non_thunderclap = bool(
            re.search(r"\b(?:dau dau du doi|dau dau rat nhieu|dau dau nang|dau du doi)\b", norm)
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
                    "Đau đầu dữ dội hoặc xuất hiện sau va đập/chấn thương đầu cần được đánh giá sớm, ngay cả khi hiện chưa có dấu hiệu thần kinh rõ."
                ),
                suggested_action=(
                    "Sắp xếp khám trong ngày. Nếu xuất hiện lơ mơ, nôn lặp lại, yếu liệt, nói khó, co giật, ngất hoặc đau tăng nhanh thì gọi 115 ngay."
                ),
                red_flags=urgent_flags,
            )

        # 6. Common / benign lifestyle patterns.
        sleep_or_screen = bool(
            re.search(
                r"\b(?:thuc khuya|thieu ngu|nhin man hinh|man hinh ca ngay|moi mat|cang thang|stress)\b",
                norm,
            )
        )

        if sleep_or_screen:
            return DomainAssessment(
                risk_level="ROUTINE",
                subtype="tension_or_lifestyle_headache",
                rationale=(
                    "Đau đầu sau thức khuya, thiếu ngủ hoặc làm việc với màn hình kéo dài có thể phù hợp với căng đầu-cổ hoặc mỏi thị giác, "
                    "khi không có các dấu hiệu thần kinh cảnh báo."
                ),
                suggested_action="Nghỉ ngơi, ngủ đủ giấc, giảm thời gian màn hình, uống đủ nước và theo dõi thêm.",
                red_flags=[],
            )

        return DomainAssessment(
            risk_level="ROUTINE",
            subtype="common_headache",
            rationale="Đau đầu nhẹ hoặc vừa hiện chưa kèm dấu hiệu thần kinh, sốt cao-cứng cổ hay chấn thương đầu được mô tả.",
            suggested_action="Nghỉ ngơi trong không gian yên tĩnh, uống đủ nước và theo dõi diễn tiến.",
            red_flags=[],
        )
