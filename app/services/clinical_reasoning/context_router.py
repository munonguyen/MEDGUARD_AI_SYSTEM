"""Clinical context router for MedGuard AI V28.2.

Transforms conversational input into structured evidence:
symptom + context + severity + associated findings + negative findings -> risk.

V28.2 makes evidence mention-aware: the latest current mention wins when a
finding changes state inside one utterance, while hypothetical mentions remain
separate from current findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterable

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

    def _mentions(
        self,
        norm: str,
        patterns: Iterable[str],
        conditional_start: int = -1,
    ) -> tuple[list[tuple[int, bool]], bool]:
        """Return current mentions ``(position, negated)`` and hypothetical flag."""
        current: list[tuple[int, bool]] = []
        hypothetical = False
        for pattern in patterns:
            for match in re.finditer(rf"\b{re.escape(pattern)}\b", norm):
                if conditional_start >= 0 and match.start() > conditional_start:
                    hypothetical = True
                    continue
                current.append(
                    (match.start(), self.negation_engine.is_negated_at(norm, match.start()))
                )
        return current, hypothetical

    def _latest_current_affirmed(
        self,
        norm: str,
        patterns: Iterable[str],
        conditional_start: int = -1,
    ) -> bool:
        current, _ = self._mentions(norm, patterns, conditional_start)
        if not current:
            return False
        _, negated = max(current, key=lambda item: item[0])
        return not negated

    def parse(self, text: str) -> ClinicalContextResult:
        norm = normalize_search_text(text)
        result = ClinicalContextResult()

        result.is_hypothetical = bool(self._HYPOTHETICAL_QUESTION.search(norm))
        conditional_match = self._HYPOTHETICAL_START.search(norm) if result.is_hypothetical else None
        conditional_start = conditional_match.start() if conditional_match else -1

        # Extract every mention and use the latest *current* mention as the state.
        # This correctly handles transitions such as:
        # "lúc đầu không khó thở nhưng giờ khó thở" -> current positive.
        for key, patterns in self.TERMS.items():
            current, hypothetical = self._mentions(norm, patterns, conditional_start)
            if hypothetical:
                result.hypothetical_findings[key] = True
            if not current:
                continue
            _, negated = max(current, key=lambda item: item[0])
            if negated:
                result.negative_findings[key] = True
            else:
                result.positive_findings[key] = True

        # Triggers must also be current and affirmed. Keyword presence alone is
        # insufficient ("không tập gym", "không uống thuốc", etc.).
        if result.positive_findings.get("exercise"):
            result.triggers.append("exercise_related")
        if self._latest_current_affirmed(
            norm, ("thuc khuya", "thieu ngu", "mat ngu"), conditional_start
        ):
            result.triggers.append("sleep_deprivation")
        if self._latest_current_affirmed(
            norm, ("ngoi lau", "ngoi may tinh", "ngoi ca ngay"), conditional_start
        ):
            result.triggers.append("prolonged_sitting")
        if self._latest_current_affirmed(
            norm, ("uong ruou", "uong bia", "nhau"), conditional_start
        ):
            result.triggers.append("alcohol_intake")
        if self._latest_current_affirmed(
            norm, ("uong thuoc", "sau khi uong"), conditional_start
        ):
            result.triggers.append("medication_ingestion")
        if self._latest_current_affirmed(
            norm, ("hoa chat", "tay rua", "phong kin"), conditional_start
        ):
            result.triggers.append("chemical_exposure")

        for key in result.positive_findings:
            if key != "exercise":
                result.symptoms.append(key)

        # Severity is based on the latest affirmed intensity description rather
        # than raw keyword presence. "Không đau dữ dội, chỉ hơi đau" -> mild.
        intensity_mentions: list[tuple[int, str]] = []
        for label, patterns in (
            ("high", ("du doi nhat", "rat du doi", "du doi", "rat dau")),
            ("mild", ("nhe", "am i", "hoi")),
        ):
            for pattern in patterns:
                for match in re.finditer(rf"\b{re.escape(pattern)}\b", norm):
                    if conditional_start >= 0 and match.start() > conditional_start:
                        continue
                    if not self.negation_engine.is_negated_at(norm, match.start()):
                        intensity_mentions.append((match.start(), label))
        if intensity_mentions:
            _, level = max(intensity_mentions, key=lambda item: item[0])
            result.severity["level"] = level

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
        # Pure contingency questions must not be converted into current disease findings.
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

        # Route allergy/toxic exposure only from affirmed structured evidence or
        # affirmed triggers. Negated raw words such as "không dị ứng" or
        # "không tiếp xúc hóa chất" cannot hijack a chest-pain presentation.
        explicit_allergy_context = any(
            result.positive_findings.get(key)
            for key in ("rash", "angioedema", "throat_tightness")
        ) or any(
            trigger in result.triggers
            for trigger in ("medication_ingestion", "chemical_exposure")
        )
        if explicit_allergy_context:
            return self.allergy_reasoner.evaluate(text, result)

        if result.positive_findings.get("chest_pain"):
            return self.chest_reasoner.evaluate(text, result)

        # Dyspnea without chest pain can still belong to the respiratory reasoner.
        # The reasoner itself verifies whether allergy/chemical exposure is affirmed.
        if result.positive_findings.get("shortness_of_breath"):
            return self.allergy_reasoner.evaluate(text, result)

        if result.positive_findings.get("headache"):
            return self.headache_reasoner.evaluate(text, result)

        if result.positive_findings.get("back_pain"):
            return self.back_reasoner.evaluate(text, result)

        if result.positive_findings.get("muscle_pain"):
            return self.muscle_reasoner.evaluate(text, result)

        return DomainAssessment(
            risk_level="ROUTINE",
            subtype="general_clinical_query",
            rationale="Yêu cầu tư vấn sức khỏe thông thường; dữ kiện hiện tại chưa ghi nhận dấu hiệu nguy cơ cao, nhưng các dấu hiệu chưa được hỏi tới vẫn là chưa biết.",
            suggested_action="Theo dõi diễn tiến và đi khám nếu các triệu chứng kéo dài hoặc tăng nặng.",
            red_flags=[],
        )
