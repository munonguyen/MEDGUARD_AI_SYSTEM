from __future__ import annotations

from dataclasses import dataclass
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
        pattern = rf"{re.escape(alias)}.{{0,30}}?(am tinh|duong tinh|\(-\)|\(\+\)|khong phan ung|phan ung)"
        match = re.search(pattern, norm)
        if not match:
            continue
        token = match.group(1)
        if token in {"am tinh", "(-)", "khong phan ung"}:
            return "NEGATIVE" if token != "khong phan ung" else "NON_REACTIVE"
        return "POSITIVE" if token != "phan ung" else "REACTIVE"
    return "UNKNOWN"


def _numeric_after(norm: str, aliases: tuple[str, ...], units: str = r"iu/l|miu/ml|iu/ml|u/l|ui/l|ui/ml") -> tuple[float | None, str | None]:
    for alias in aliases:
        match = re.search(
            rf"{re.escape(alias)}.{{0,40}}?(\d+(?:[.,]\d+)?)\s*({units})?",
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


def _fasting_glucose_value(norm: str) -> tuple[float | None, str | None]:
    aliases = ("duong huyet luc doi", "glucose luc doi", "fasting glucose", "fasting plasma glucose")
    value, unit = _numeric_after(norm, aliases, units=r"mmol/l|mg/dl")
    if value is not None:
        return value, unit
    # Natural Vietnamese often puts the value after "của tôi là".
    if any(alias in norm for alias in aliases):
        match = re.search(r"\b(?:la|=)?\s*(\d+(?:[.,]\d+)?)\s*(mmol/l|mg/dl)\b", norm)
        if match:
            return float(match.group(1).replace(",", ".")), match.group(2)
    return None, None


def interpret_laboratory_text(text: str) -> LabInterpretation:
    """Return bounded explanations for supported laboratory results.

    This component explains what a result can and cannot imply; it never turns a
    single laboratory value into a definitive diagnosis or a medication order.
    Independent red-flag/triage logic may still raise urgency when the narrative
    contains acute symptoms.
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

        return LabInterpretation(
            observations=observations,
            summary="Đây là câu hỏi diễn giải xét nghiệm viêm gan B, không phải một tình huống cấp tính chỉ dựa trên các chỉ số đã cung cấp.",
            interpretation_points=tuple(points),
            missing_information=tuple(missing),
            prohibited_actions=("Không tự mua hoặc tự bắt đầu thuốc kháng virus chỉ dựa trên các kết quả này.",),
            clarifying_questions=tuple(dict.fromkeys(questions)),
            confidence=min(confidence, 0.95),
        )

    # ALT is a marker of hepatocellular injury, not a diagnosis by itself.
    if re.search(r"(?<![a-z0-9])alt(?![a-z0-9])", norm) or "men gan alt" in norm:
        value, unit = _numeric_after(norm, ("alt",), units=r"u/l|ui/l|iu/l")
        says_high = any(marker in norm for marker in ("cao", "tang", "vuot nguong", "bat thuong"))
        observations = (LabObservation("ALT", value_numeric=value, unit=unit),)
        points = [
            "ALT tăng cho thấy có thể có tổn thương hoặc kích thích tế bào gan, nhưng riêng ALT không đủ để kết luận bạn mắc một bệnh gan cụ thể.",
            "Mức độ cần được đọc theo giá trị thực tế và khoảng tham chiếu của phòng xét nghiệm; bối cảnh thuốc/thực phẩm bổ sung, rượu bia, cân nặng và triệu chứng cũng quan trọng.",
        ]
        if value is None:
            points.append("Bạn mới cho biết ALT 'cao' nên chưa thể đánh giá mức tăng nhẹ hay rõ.")
        missing = [] if value is not None else ["giá trị ALT", "đơn vị", "khoảng tham chiếu"]
        missing.extend(["AST và các xét nghiệm gan liên quan nếu có", "thuốc/thực phẩm bổ sung và mức sử dụng rượu bia"])
        return LabInterpretation(
            observations=observations,
            summary=(
                "ALT cao không đồng nghĩa chắc chắn với bệnh gan và cũng không cho biết nguyên nhân chỉ từ một chỉ số."
                if says_high or value is None
                else "ALT cần được diễn giải theo giá trị, khoảng tham chiếu và bối cảnh lâm sàng."
            ),
            interpretation_points=tuple(points),
            missing_information=tuple(missing),
            prohibited_actions=("Không tự ngừng thuốc kê đơn hoặc tự dùng thuốc/bổ sung 'bổ gan' chỉ dựa vào ALT.",),
            clarifying_questions=(
                "ALT là bao nhiêu U/L và giới hạn trên của phòng xét nghiệm là bao nhiêu?",
                "Bạn có vàng da, nước tiểu sẫm, đau bụng nhiều, nôn nhiều hoặc lơ mơ không?",
            ),
            confidence=0.80 if says_high or value is not None else 0.70,
        )

    glucose_value, glucose_unit = _fasting_glucose_value(norm)
    if glucose_value is not None:
        mmol_value = glucose_value
        if glucose_unit == "mg/dl":
            mmol_value = glucose_value / 18.0
        points = [
            "Một kết quả đường huyết lúc đói ở ngưỡng cao có thể làm tăng nghi ngờ rối loạn đường huyết, nhưng không nên tự chẩn đoán chỉ từ một con số đơn lẻ.",
            "Trong thực hành lâm sàng, đường huyết tương lúc đói khoảng từ 7,0 mmol/L (126 mg/dL) trở lên nằm trong vùng chẩn đoán đái tháo đường; khi không có tăng đường huyết rõ kèm triệu chứng điển hình, kết quả thường cần được xác nhận theo quy trình chẩn đoán phù hợp.",
        ]
        if mmol_value >= 7.0:
            summary = "Kết quả bạn cung cấp nằm trong vùng cần được bác sĩ xác nhận và đánh giá thêm, không phải bằng chứng đủ để tự kết luận chẩn đoán."
        else:
            summary = "Kết quả cần được đối chiếu với khoảng tham chiếu và các xét nghiệm/bối cảnh khác trước khi kết luận."
        return LabInterpretation(
            observations=(LabObservation("fasting_glucose", value_numeric=glucose_value, unit=glucose_unit),),
            summary=summary,
            interpretation_points=tuple(points),
            missing_information=("điều kiện nhịn đói trước xét nghiệm", "HbA1c hoặc kết quả lặp lại nếu bác sĩ chỉ định"),
            prohibited_actions=("Không tự bắt đầu thuốc hạ đường huyết chỉ dựa trên một kết quả xét nghiệm.",),
            clarifying_questions=(
                "Bạn đã nhịn ăn ít nhất khoảng 8 giờ trước khi lấy máu chưa?",
                "Bạn có HbA1c hoặc một kết quả đường huyết lúc đói khác để đối chiếu không?",
            ),
            confidence=0.88,
        )

    return LabInterpretation(
        summary="Đã nhận diện đây là yêu cầu diễn giải xét nghiệm nhưng chưa đủ cấu trúc để giải thích an toàn.",
        missing_information=("tên xét nghiệm", "giá trị", "đơn vị hoặc khoảng tham chiếu"),
        clarifying_questions=("Bạn gửi tên xét nghiệm, giá trị, đơn vị và khoảng tham chiếu trên phiếu giúp mình nhé.",),
        confidence=0.45,
    )
