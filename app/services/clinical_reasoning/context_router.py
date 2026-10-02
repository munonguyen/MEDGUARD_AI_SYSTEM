"""Clinical context router for MedGuard AI V28.1.

Replaces naive keyword-only urgency decisions with structured evidence:
symptom + context + severity + duration + associated findings + negative findings -> calibrated risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from app.services.clinical_text import normalize_search_text
from app.services.clinical_reasoning.domains.allergy_respiratory import AllergyRespiratoryReasoner
from app.services.clinical_reasoning.domains.back_pain import BackPainReasoner
from app.services.clinical_reasoning.domains.chest_pain import ChestPainReasoner
from app.services.clinical_reasoning.domains.headache import DomainAssessment, HeadacheReasoner
from app.services.clinical_reasoning.domains.metabolic import MetabolicReasoner
from app.services.clinical_reasoning.domains.muscle_pain import MusclePainReasoner
from app.services.clinical_reasoning.negation_engine import NegationEngine


@dataclass
class ClinicalContextResult:
    symptoms: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    severity: dict[str, str] = field(default_factory=dict)
    positive_findings: dict[str, bool] = field(default_factory=dict)
    negative_findings: dict[str, bool] = field(default_factory=dict)
    hypothetical_findings: dict[str, bool] = field(default_factory=dict)
    risk_features: list[str] = field(default_factory=list)
    is_hypothetical: bool = False
    domain_assessment: DomainAssessment | None = None


class ClinicalContextRouter:
    """Transform conversational input into structured, scope-aware clinical evidence."""

    TERMS = {
        "chest_pain": ("dau nguc", "tuc nguc", "nang nguc", "ep nguc"),
        "headache": ("dau dau", "nhuc dau"),
        "back_pain": ("dau lung", "moi lung"),
        "muscle_pain": ("dau co", "moi co", "cang co"),
        "leg_weakness": ("yeu chan", "liet chan", "kho nhac ban chan", "yeu hai chan"),
        "shortness_of_breath": ("kho tho", "hut hoi", "tho gap"),
        "sweating": ("va mo hoi", "do mo hoi", "toat mo hoi"),
        "radiation": ("lan tay", "lan ham", "lan vai", "lan lung"),
        "exercise": ("tap gym", "tap luyen", "chong day", "van dong", "nang ta", "chay bo"),
        "fever": ("sot",),
        "angioedema": ("sung moi", "sung mat", "sung luoi", "phu mat"),
        "throat_tightness": ("nghen co hong", "nghet hong", "nghen hong"),
        "rash": ("me day", "phat ban", "noi man"),
        "dizziness": ("chong mat", "xay xam", "choang"),
        "incontinence": ("tieu khong tu chu", "bi tieu", "mat kiem soat tieu tien"),
    }

    _HYPOTHETICAL_START = re.compile(r"\b(?:neu nhu|neu|gia su|truong hop|lo may)\b")
    _HYPOTHETICAL_QUESTION = re.compile(
        r"\b(?:neu|neu nhu|truong hop|gia su|lo may)\b.*?\b(?:thi phai lam gi|thi xu tri the nao|nen lam gi|can lam gi|lam gi)\b"
    )

    def __init__(self) -> None:
        self.negation_engine = NegationEngine()
        self.headache_reasoner = HeadacheReasoner()
        self.chest_reasoner = ChestPainReasoner()
        self.back_reasoner = BackPainReasoner()
        self.muscle_reasoner = MusclePainReasoner()
        self.allergy_reasoner = AllergyRespiratoryReasoner()
        self.metabolic_reasoner = MetabolicReasoner()

    def parse(self, text: str) -> ClinicalContextResult:
        norm = normalize_search_text(text)
        result = ClinicalContextResult()

        result.is_hypothetical = bool(self._HYPOTHETICAL_QUESTION.search(norm))
        conditional_match = self._HYPOTHETICAL_START.search(norm) if result.is_hypothetical else None
        conditional_start = conditional_match.start() if conditional_match else -1

        # Extract findings with both negation and hypothetical-scope awareness.
        # A symptom mentioned only inside "Nếu ... thì làm gì?" is a contingency,
        # not a present finding.
        for key, patterns in self.TERMS.items():
            matched = None
            matched_pattern = None
            for pattern in patterns:
                candidate = re.search(rf"\b{re.escape(pattern)}\b", norm)
                if candidate:
                    matched = candidate
                    matched_pattern = pattern
                    break
            if not matched or not matched_pattern:
                continue

            if conditional_start >= 0 and matched.start() > conditional_start:
                result.hypothetical_findings[key] = True
                continue

            if self.negation_engine.detect(norm, matched_pattern):
                result.negative_findings[key] = True
            else:
                result.positive_findings[key] = True

        # Extract triggers from current (non-hypothetical) narrative.
        if result.positive_findings.get("exercise"):
            result.triggers.append("exercise_related")
        if any(w in norm for w in ("thuc khuya", "thieu ngu", "mat ngu")):
            result.triggers.append("sleep_deprivation")
        if any(w in norm for w in ("ngoi lau", "ngoi may tinh", "ngoi ca ngay")):
            result.triggers.append("prolonged_sitting")
        if any(w in norm for w in ("uong ruou", "uong bia", "nhau")):
            result.triggers.append("alcohol_intake")
        if any(w in norm for w in ("uong thuoc", "sau khi uong")):
            result.triggers.append("medication_ingestion")
        if any(w in norm for w in ("hoa chat", "tay rua", "phong kin")):
            result.triggers.append("chemical_exposure")

        for key in result.positive_findings:
            if key != "exercise":
                result.symptoms.append(key)

        if any(word in norm for word in ("du doi", "rat dau", "chua tung bi", "du doi nhat")):
            result.severity["level"] = "high"
        elif any(word in norm for word in ("nhe", "am i", "hoi")):
            result.severity["level"] = "mild"

        assessment = self._evaluate_domain(text, norm, result)
        result.domain_assessment = assessment

        flags = list(assessment.red_flags if assessment else [])
        positive = result.positive_findings

        if positive.get("chest_pain") and any(
            positive.get(x) for x in ("shortness_of_breath", "sweating", "radiation")
        ):
            if "cardiac_warning_pattern" not in flags:
                flags.append("cardiac_warning_pattern")

        if positive.get("back_pain") and (positive.get("leg_weakness") or positive.get("incontinence")):
            if "spinal_neurological_warning" not in flags:
                flags.append("spinal_neurological_warning")

        if positive.get("headache") and result.severity.get("level") == "high":
            if "severe_headache_pattern" not in flags:
                flags.append("severe_headache_pattern")

        result.risk_features = flags
        return result

    def _evaluate_domain(self, text: str, norm: str, result: ClinicalContextResult) -> DomainAssessment:
        # Pure contingency questions must not be converted into current disease
        # findings. They receive safety-net guidance only.
        if result.is_hypothetical and result.hypothetical_findings and not result.positive_findings:
            return DomainAssessment(
                risk_level="ROUTINE",
                subtype="contingency_safety_guidance",
                rationale=(
                    "Các dấu hiệu trong câu hỏi đang được nêu dưới dạng giả định/dự phòng, không phải triệu chứng hiện tại đã được xác nhận."
                ),
                suggested_action=(
                    "Nếu các dấu hiệu giả định thực sự xuất hiện, hãy làm theo ngưỡng xử trí tương ứng; với khó thở, sưng môi/lưỡi, nghẹn họng, ngất hoặc đau ngực nặng thì cần gọi cấp cứu."
                ),
                red_flags=[],
            )

        if any(w in norm for w in ("duong huyet", "glucose", "mg/dl", "mg dl")):
            return self.metabolic_reasoner.evaluate(text, result)

        current_allergy_signal = any(
            result.positive_findings.get(key)
            for key in ("rash", "angioedema", "throat_tightness", "shortness_of_breath")
        )
        if current_allergy_signal or any(w in norm for w in ("ong dot", "di ung", "hoa chat")):
            return self.allergy_reasoner.evaluate(text, result)

        is_skin_rash = any(w in norm for w in ("ban lan", "me day", "phat ban")) and "nguc" in norm
        if result.positive_findings.get("chest_pain") and not is_skin_rash:
            return self.chest_reasoner.evaluate(text, result)

        if result.positive_findings.get("headache"):
            return self.headache_reasoner.evaluate(text, result)

        if result.positive_findings.get("back_pain"):
            return self.back_reasoner.evaluate(text, result)

        if result.positive_findings.get("muscle_pain"):
            return self.muscle_reasoner.evaluate(text, result)

        return DomainAssessment(
            risk_level="ROUTINE",
            subtype="general_clinical_query",
            rationale="Yêu cầu tư vấn sức khỏe thông thường, chưa ghi nhận dấu hiệu nguy cơ cao từ dữ kiện hiện có.",
            suggested_action="Theo dõi diễn tiến và đi khám nếu các triệu chứng kéo dài hoặc tăng nặng.",
            red_flags=[],
        )
