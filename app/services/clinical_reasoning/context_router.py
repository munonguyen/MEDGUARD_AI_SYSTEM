"""Clinical context router for MedGuard AI V28.1.

Replaces naive keyword-only urgency decisions with structured evidence:
symptom + context + severity + duration + associated findings + negative findings -> calibrated risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

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
    risk_features: list[str] = field(default_factory=list)
    is_hypothetical: bool = False
    domain_assessment: DomainAssessment | None = None


class ClinicalContextRouter:
    """Clinical Context Router transforming conversational input into structured medical evidence."""

    # Patterns normalized without diacritics
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

        # Detect hypothetical / safety-net questions
        result.is_hypothetical = bool(
            re.search(
                r"\b(?:neu|neu nhu|truong hop|gia su|lo may)\b.*?\b(?:thi phai lam gi|thi xu tri the nao|nen lam gi|can lam gi|lam gi)\b",
                norm,
            )
        )

        # Extract positive and negative findings with scope-aware NegationEngine
        for key, patterns in self.TERMS.items():
            found_pattern = None
            for p in patterns:
                if re.search(rf"\b{re.escape(p)}\b", norm):
                    found_pattern = p
                    break

            if not found_pattern:
                continue

            is_negated = self.negation_engine.detect(norm, found_pattern)
            if is_negated:
                result.negative_findings[key] = True
            else:
                result.positive_findings[key] = True

        # Extract triggers
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
            if key not in {"exercise"}:
                result.symptoms.append(key)

        # Severity indicators
        if any(word in norm for word in ("du doi", "rat dau", "chua tung bi", "du doi nhat")):
            result.severity["level"] = "high"
        elif any(word in norm for word in ("nhe", "am i", "hoi")):
            result.severity["level"] = "mild"

        # Domain-specific evaluation
        assessment = self._evaluate_domain(text, norm, result)
        result.domain_assessment = assessment

        # Combine red flags from domain assessment
        flags = list(assessment.red_flags if assessment else [])

        # Additional multi-finding safety combinations
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
        # Check metabolic/glucose first if readings or hypo signs present
        if any(w in norm for w in ("duong huyet", "glucose", "mg/dl", "mg dl")):
            return self.metabolic_reasoner.evaluate(text, result)

        # Check allergy/respiratory
        if any(w in norm for w in ("me day", "phat ban", "sung moi", "sung mat", "ong dot", "di ung", "hoa chat")):
            return self.allergy_reasoner.evaluate(text, result)

        # Check chest symptoms (exclude rash on chest)
        is_skin_rash = any(w in norm for w in ("ban lan", "me day", "phat ban")) and "nguc" in norm
        if result.positive_findings.get("chest_pain") and not is_skin_rash:
            return self.chest_reasoner.evaluate(text, result)

        # Check headache
        if result.positive_findings.get("headache"):
            return self.headache_reasoner.evaluate(text, result)

        # Check back pain
        if result.positive_findings.get("back_pain"):
            return self.back_reasoner.evaluate(text, result)

        # Check muscle pain
        if result.positive_findings.get("muscle_pain"):
            return self.muscle_reasoner.evaluate(text, result)

        # Default fallback assessment
        return DomainAssessment(
            risk_level="ROUTINE",
            subtype="general_clinical_query",
            rationale="Yêu cầu tư vấn sức khỏe thông thường, chưa ghi nhận dấu hiệu nguy cơ cao.",
            suggested_action="Theo dõi diễn tiến và đi khám nếu các triệu chứng kéo dài hoặc tăng nặng.",
            red_flags=[],
        )
