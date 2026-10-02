from __future__ import annotations

import re

from app.models.clinical_task import ClinicalTask, ClinicalTaskDecision
from app.services.clinical_text import normalize_search_text


# Strong laboratory-result markers can identify the work type directly. Generic
# words such as "xét nghiệm" are handled separately because "có nên đi xét
# nghiệm không?" is a care-planning question, not a request to interpret a lab.
_STRONG_LAB_MARKERS = (
    "hbsag",
    "anti-hbs",
    "anti hbs",
    "anti-hbc",
    "anti hbc",
    "ket qua xet nghiem",
    "chi so xet nghiem",
    "men gan",
    "ast",
    "alt",
    "creatinin",
    "creatinine",
    "hba1c",
    "duong huyet luc doi",
    "glucose luc doi",
    "fasting glucose",
    "fasting plasma glucose",
    "cholesterol",
    "triglycerid",
    "triglyceride",
)
_GENERIC_LAB_MARKERS = ("xet nghiem", "xet nghiem mau")
_LAB_RESULT_CUES = (
    "ket qua",
    "chi so",
    "cao",
    "thap",
    "tang",
    "giam",
    "am tinh",
    "duong tinh",
    "binh thuong",
    "bat thuong",
    "mmol/l",
    "mg/dl",
    "u/l",
    "ui/l",
)

_EXPOSURE_MARKERS = (
    "kem boi",
    "kem duong",
    "kem nghe",
    "my pham",
    "serum",
    "mat na",
    "thuoc boi",
    "san pham boi",
    "hoa chat",
    "sua rua mat",
    "thuoc nhuom",
)

_EXPOSURE_REACTION_MARKERS = (
    "do rat",
    "cham chich",
    "ngua",
    "noi mun nuoc",
    "mun nuoc",
    "sung",
    "phat ban",
    "noi man",
    "bong rat",
    "kich ung",
)

_MEDICATION_MARKERS = (
    "tuong tac thuoc",
    "an toan thuoc",
    "lieu dung",
    "qua lieu",
    "uong chung",
    "dung chung",
    "di ung thuoc",
    "thuoc co dung duoc",
    "thuoc ngu",
)

_MONITORING_MARKERS = ("spo2", "huyet ap", "nhip tim", "nhiet do", "duong huyet")
_FOLLOWUP_MARKERS = ("tai kham", "lich kham", "follow up", "follow-up", "lich hen")


def _contains_marker(norm: str, marker: str) -> bool:
    """Match task markers as lexical units, never arbitrary substrings."""
    return re.search(
        rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])",
        norm,
    ) is not None


def _has_laboratory_result_language(norm: str) -> tuple[bool, list[str]]:
    strong_hits = [marker for marker in _STRONG_LAB_MARKERS if _contains_marker(norm, marker)]
    qualitative_result = bool(
        re.search(r"\b[a-z][a-z0-9-]{1,20}\s*(?:am tinh|duong tinh|\(-\)|\(\+\))", norm)
    )
    generic_lab = any(_contains_marker(norm, marker) for marker in _GENERIC_LAB_MARKERS)
    result_cue = any(_contains_marker(norm, marker) for marker in _LAB_RESULT_CUES) or bool(
        re.search(r"\b\d+(?:[.,]\d+)?\s*(?:mmol/l|mg/dl|u/l|ui/l|g/l|%)\b", norm)
    )

    is_result_interpretation = bool(strong_hits or qualitative_result or (generic_lab and result_cue))
    reasons = []
    if strong_hits:
        reasons.append("named_laboratory_marker_detected")
    if qualitative_result or (generic_lab and result_cue):
        reasons.append("laboratory_result_language_detected")
    return is_result_interpretation, reasons


def resolve_clinical_task(text: str) -> ClinicalTaskDecision:
    """Classify the kind of clinical work requested by the user.

    This router intentionally does not determine urgency. Safety/triage remain
    independent and may raise the care level later without changing the task.
    """
    norm = normalize_search_text(text)

    is_lab_result, lab_reasons = _has_laboratory_result_language(norm)
    if is_lab_result:
        return ClinicalTaskDecision(
            task=ClinicalTask.LAB_INTERPRETATION,
            confidence=0.96,
            reasons=lab_reasons or ["laboratory_result_language_detected"],
            domain="laboratory",
        )

    has_exposure = any(_contains_marker(norm, marker) for marker in _EXPOSURE_MARKERS)
    reaction_hits = [
        marker for marker in _EXPOSURE_REACTION_MARKERS if _contains_marker(norm, marker)
    ]
    if has_exposure and reaction_hits:
        return ClinicalTaskDecision(
            task=ClinicalTask.EXPOSURE_REACTION,
            confidence=0.95,
            reasons=["topical_or_chemical_exposure_with_reaction"],
            domain="dermatology_exposure",
        )

    if any(_contains_marker(norm, marker) for marker in _MEDICATION_MARKERS) or bool(
        re.search(r"\bco nen\s+(?:dung|uong|tu mua)\b.{0,60}\bthuoc\b", norm)
    ):
        return ClinicalTaskDecision(
            task=ClinicalTask.MEDICATION_SAFETY,
            confidence=0.94,
            reasons=["medication_safety_request"],
            domain="medication",
        )

    if any(_contains_marker(norm, marker) for marker in _MONITORING_MARKERS) and bool(re.search(r"\d", norm)):
        return ClinicalTaskDecision(
            task=ClinicalTask.MONITORING,
            confidence=0.90,
            reasons=["physiologic_measurement_detected"],
            domain="monitoring",
        )

    if any(_contains_marker(norm, marker) for marker in _FOLLOWUP_MARKERS):
        return ClinicalTaskDecision(
            task=ClinicalTask.FOLLOWUP,
            confidence=0.88,
            reasons=["followup_or_booking_language_detected"],
            domain="followup",
        )

    if any(_contains_marker(norm, marker) for marker in ("tang huyet ap", "cao huyet ap")) and any(
        marker in norm for marker in ("chua khoi", "khoi hoan toan", "kiem soat", "song chung")
    ):
        return ClinicalTaskDecision(
            task=ClinicalTask.CHRONIC_CONDITION,
            confidence=0.90,
            reasons=["chronic_condition_education_request"],
            domain="chronic_condition",
        )

    if any(
        _contains_marker(norm, marker)
        for marker in (
            "dau",
            "sot",
            "kho tho",
            "buon non",
            "non",
            "chong mat",
            "te",
            "yeu",
            "sung",
            "do",
            "ngua",
            "phat ban",
            "chay mau",
            "co giat",
            "ngat",
            "met moi",
            "met",
            "suy nhuoc",
            "mat ngu",
        )
    ):
        return ClinicalTaskDecision(
            task=ClinicalTask.ACUTE_SYMPTOM,
            confidence=0.80,
            reasons=["symptom_language_detected"],
            domain="clinical_symptom",
        )

    return ClinicalTaskDecision(
        task=ClinicalTask.GENERAL_MEDICAL,
        confidence=0.55,
        reasons=["no_specific_clinical_task_signal"],
        domain="general",
    )
