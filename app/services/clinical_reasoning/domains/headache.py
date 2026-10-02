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
    """Evaluates headache presentations to distinguish sleep/tension from neuro emergencies."""

    def evaluate(self, text: str, clinical_context: Any) -> DomainAssessment:
        norm = normalize_search_text(text)
        red_flags: list[str] = []

        # 1. Thunderclap / Sudden severe headache
        sudden_severe = bool(
            re.search(
                r"\b(?:dot ngot|set danh|du doi nhat|chua tung bi|rat du doi)\b",
                norm,
            )
        ) and any(w in norm for w in ("dau dau", "dau", "con dau"))

        # 2. Focal neurological deficit
        focal_neuro = bool(
            re.search(
                r"\b(?:meo mieng|lech mieng|noi ngong|yeu tay|yeu chan|yeu nua nguoi|mat thi luc|nhin mo dot ngot|co giat|hon me)\b",
                norm,
            )
        )

        # 3. Infection / Meningismus
        meningismus = "sot" in norm and any(w in norm for w in ("cung co", "co cung", "lu lan"))

        if sudden_severe:
            red_flags.append("thunderclap_headache")
        if focal_neuro:
            red_flags.append("focal_neurological_deficit")
        if meningismus:
            red_flags.append("meningeal_signs")

        if red_flags:
            return DomainAssessment(
                risk_level="EMERGENCY",
                subtype="neurological_emergency",
                rationale=(
                    "Đau đầu khởi phát đột ngột rất dữ dội hoặc xuất hiện cùng dấu hiệu thần kinh khu trú (yếu liệt, nói ngọng, co giật) "
                    "là cảnh báo biến cố thần kinh cấp tính cần được đánh giá y tế khẩn cấp tại bệnh viện."
                ),
                suggested_action="Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức; không tự lái xe.",
                red_flags=red_flags,
            )

        # Common / benign causes
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
                    "Đau đầu sau khi thức khuya, thiếu ngủ hoặc làm việc với màn hình kéo dài thường liên quan đến căng cơ vùng đầu cổ "
                    "hoặc mỏi điều tiết thị giác, hiện tại chưa ghi nhận các dấu hiệu thần kinh cảnh báo."
                ),
                suggested_action="Nghỉ ngơi, ngủ đủ giấc, hạn chế ánh sáng màn hình và theo dõi thêm.",
                red_flags=[],
            )

        return DomainAssessment(
            risk_level="ROUTINE",
            subtype="common_headache",
            rationale="Đau đầu mức độ nhẹ hoặc vừa không kèm các dấu hiệu thần kinh hay sốt cao cứng cổ.",
            suggested_action="Nghỉ ngơi trong không gian yên tĩnh, uống đủ nước và theo dõi diễn tiến.",
            red_flags=[],
        )
