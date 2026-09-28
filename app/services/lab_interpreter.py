from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Literal

from app.services.clinical_text import normalize_search_text


Qualitative = Literal["POSITIVE", "NEGATIVE", "REACTIVE", "NON_REACTIVE", "UNKNOWN"]


@dataclass(frozen=True)
class LabObservation:
    test_name: str
    qualitative: Qualitative = "UNKNOWN"
    value_numeric: float | None = None
    unit: str | None = None


@dataclass(frozen=True)
class LabInterpretation:
    clinical_task: str = "LAB_INTERPRETATION"
    urgency: str = "ROUTINE"
    domain: str = "laboratory"
    observations: tuple[LabObservation, ...] = ()
    summary: str = ""
    interpretation_points: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    prohibited_actions: tuple[str, ...] = ()
    clarifying_questions: tuple[str, ...] = ()
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "clinical_task": self.clinical_task,
            "urgency": self.urgency,
            "domain": self.domain,
            "observations": [
                {
                    "test_name": item.test_name,
                    "qualitative": item.qualitative,
                    "value_numeric": item.value_numeric,
                    "unit": item.unit,
                }
                for item in self.observations
            ],
            "summary": self.summary,
            "interpretation_points": list(self.interpretation_points),
            "missing_information": list(self.missing_information),
            "prohibited_actions": list(self.prohibited_actions),
            "clarifying_questions": list(self.clarifying_questions),
            "confidence": self.confidence,
        }


def _qualitative(norm: str, aliases: tuple[str, ...]) -> Qualitative:
    for alias in aliases:
        # Keep the test/result relation local so one positive marker is not
        # accidentally assigned to every test mentioned in the sentence.
        pattern = rf"{re.escape(alias)}.{{0,30}}?(am tinh|duong tinh|\(-\)|\(\+\)|khong phan ung|phan ung)"
        match = re.search(pattern, norm)
        if not match:
            continue
        token = match.group(1)
        if token in {"am tinh", "(-)", "khong phan ung"}:
            return "NEGATIVE" if token != "khong phan ung" else "NON_REACTIVE"
        return "POSITIVE" if token != "phan ung" else "REACTIVE"
    return "UNKNOWN"


def _numeric_after(norm: str, aliases: tuple[str, ...]) -> tuple[float | None, str | None]:
    for alias in aliases:
        match = re.search(
            rf"{re.escape(alias)}.{{0,40}}?(\d+(?:[.,]\d+)?)\s*(iu/l|miu/ml|iu/ml|u/l|ui/l|ui/ml)?",
            norm,
        )
        if not match:
            continue
        try:
            value = float(match.group(1).replace(",", "."))
        except ValueError:
            value = None
        return value, match.group(2)
    return None, None


def interpret_laboratory_text(text: str) -> LabInterpretation:
    """Interpret supported lab panels without routing them through acute triage.

    The interpreter returns bounded, evidence-shaped facts. It deliberately
    avoids diagnosis and medication decisions; the response agent can explain
    the structured state while respecting the prohibited-action list.
    """
    norm = normalize_search_text(text)

    hbsag_aliases = ("hbsag", "hbs ag")
    anti_hbs_aliases = ("anti-hbs", "anti hbs", "hbsab")
    anti_hbc_aliases = ("anti-hbc", "anti hbc", "hbcab", "total anti-hbc", "total anti hbc")

    mentions_hbv = any(alias in norm for alias in (*hbsag_aliases, *anti_hbs_aliases, *anti_hbc_aliases))
    if mentions_hbv:
        hbsag = _qualitative(norm, hbsag_aliases)
        anti_hbs = _qualitative(norm, anti_hbs_aliases)
        anti_hbc = _qualitative(norm, anti_hbc_aliases)
        anti_hbs_value, anti_hbs_unit = _numeric_after(norm, anti_hbs_aliases)

        observations = (
            LabObservation("HBsAg", hbsag),
            LabObservation("anti-HBs", anti_hbs, anti_hbs_value, anti_hbs_unit),
            LabObservation("total anti-HBc", anti_hbc),
        )

        points: list[str] = []
        missing: list[str] = []
        questions: list[str] = []
        confidence = 0.78

        if hbsag == "NEGATIVE":
            points.append("Kết quả HBsAg âm tính không ủng hộ tình trạng nhiễm HBV hiện tại tại thời điểm xét nghiệm.")
            confidence += 0.06
        if anti_hbs == "POSITIVE":
            points.append("Anti-HBs dương tính phù hợp với trạng thái có kháng thể bảo vệ/miễn dịch với HBV.")
            confidence += 0.06
        if anti_hbc == "UNKNOWN" and hbsag == "NEGATIVE" and anti_hbs == "POSITIVE":
            missing.append("total anti-HBc")
            questions.append("Bạn có kết quả total anti-HBc hay tiền sử tiêm vaccine viêm gan B không?")
            points.append("Cần total anti-HBc hoặc tiền sử tiêm vaccine để phân biệt miễn dịch do vaccine với nhiễm cũ đã hồi phục.")

        if hbsag == "POSITIVE":
            points.append("HBsAg dương tính cần được bác sĩ đánh giá cùng anti-HBc, men gan và bối cảnh lâm sàng để xác định tình trạng nhiễm.")
            questions.append("Bạn có kết quả total anti-HBc, HBeAg/HBV DNA hoặc men gan AST/ALT không?")

        summary = (
            "Đây là câu hỏi diễn giải xét nghiệm viêm gan B, không phải một tình huống cấp tính chỉ dựa trên các chỉ số đã cung cấp."
        )
        return LabInterpretation(
            observations=observations,
            summary=summary,
            interpretation_points=tuple(points),
            missing_information=tuple(missing),
            prohibited_actions=("Không tự mua hoặc tự bắt đầu thuốc kháng virus chỉ dựa trên các kết quả này.",),
            clarifying_questions=tuple(dict.fromkeys(questions)),
            confidence=min(confidence, 0.95),
        )

    # Unknown laboratory domain: answerability remains partial rather than
    # escalating to acute triage merely because the user is worried.
    return LabInterpretation(
        summary="Đã nhận diện đây là yêu cầu diễn giải xét nghiệm nhưng chưa đủ cấu trúc để giải thích an toàn.",
        missing_information=("tên xét nghiệm", "giá trị", "đơn vị hoặc khoảng tham chiếu"),
        clarifying_questions=("Bạn gửi tên xét nghiệm, giá trị, đơn vị và khoảng tham chiếu trên phiếu giúp mình nhé.",),
        confidence=0.45,
    )
