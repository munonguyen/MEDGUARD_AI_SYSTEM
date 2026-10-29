from __future__ import annotations

from dataclasses import dataclass

from app.services.clinical_text import normalize_search_text


@dataclass(frozen=True)
class ExposureAssessment:
    clinical_task: str = "EXPOSURE_REACTION"
    urgency: str = "ROUTINE"
    domain: str = "dermatology_exposure"
    summary: str = ""
    recommended_specialty: dict | None = None
    present_features: tuple[str, ...] = ()
    prohibited_actions: tuple[str, ...] = ()
    what_to_do_now: tuple[str, ...] = ()
    warning_signs: tuple[str, ...] = ()
    clarifying_questions: tuple[str, ...] = ()
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "clinical_task": self.clinical_task,
            "urgency": self.urgency,
            "domain": self.domain,
            "summary": self.summary,
            "recommended_specialty": self.recommended_specialty,
            "present_features": list(self.present_features),
            "prohibited_actions": list(self.prohibited_actions),
            "what_to_do_now": list(self.what_to_do_now),
            "warning_signs": list(self.warning_signs),
            "clarifying_questions": list(self.clarifying_questions),
            "confidence": self.confidence,
        }


def evaluate_exposure_reaction(text: str) -> ExposureAssessment:
    norm = normalize_search_text(text)

    feature_map = {
        "redness": ("do rat", "da do", "do da", "do mat"),
        "burning": ("rat", "bong rat"),
        "stinging": ("cham chich", "xot"),
        "vesicles": ("mun nuoc", "noi mun nuoc"),
        "itch": ("ngua",),
        "swelling": ("sung", "phu"),
        "rash": ("phat ban", "noi man", "me day"),
        "facial_location": ("da mat", "mat", "quanh mat"),
    }
    present = tuple(
        key for key, markers in feature_map.items() if any(marker in norm for marker in markers)
    )

    airway = any(marker in norm for marker in ("kho tho", "tho rit", "khan giong", "sung luoi", "phu moi", "nghet tho"))
    systemic = any(marker in norm for marker in ("va mo hoi", "choang", "ngat", "tim dap nhanh"))

    if airway:
        urgency = "EMERGENCY"
    elif "vesicles" in present or ("facial_location" in present and len(present) >= 3) or systemic:
        urgency = "URGENT"
    else:
        urgency = "ROUTINE"

    questions: list[str] = []
    if not airway:
        questions.append("Bạn có sưng môi/lưỡi, khàn giọng, khó thở hoặc phát ban lan nhanh không?")
    if "facial_location" in present:
        questions.append("Vùng da quanh mắt có sưng nhiều, đau mắt hoặc nhìn mờ không?")

    return ExposureAssessment(
        urgency=urgency,
        summary=(
            "Các biểu hiện da xuất hiện liên quan đến một sản phẩm bôi nên được xử lý như phản ứng da do phơi nhiễm cho đến khi xác định rõ tác nhân."
        ),
        recommended_specialty={"code": "DERMATOLOGY", "label": "Da liễu", "confidence": 0.9},
        present_features=present,
        prohibited_actions=("Không bôi lại sản phẩm đang nghi gây phản ứng để thử xem có dịu hơn không.",),
        what_to_do_now=(
            "Ngừng sản phẩm nghi gây phản ứng và các sản phẩm mới chưa cần thiết trên vùng da đang kích ứng.",
            "Nếu da mặt đỏ rát nhiều, có mụn nước hoặc triệu chứng kéo dài, nên được bác sĩ Da liễu đánh giá trực tiếp.",
        ),
        warning_signs=(
            "Khó thở, khàn giọng, sưng môi/lưỡi hoặc choáng/ngất cần được xử trí cấp cứu ngay.",
        ),
        clarifying_questions=tuple(dict.fromkeys(questions)),
        confidence=0.94 if present else 0.65,
    )
