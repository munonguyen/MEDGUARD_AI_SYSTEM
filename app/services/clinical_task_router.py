from __future__ import annotations

import re

from app.models.clinical_task import ClinicalTask, ClinicalTaskDecision
from app.services.clinical_text import normalize_search_text


_LAB_MARKERS = (
    "hbsag",
    "anti-hbs",
    "anti hbs",
    "anti-hbc",
    "anti hbc",
    "xet nghiem",
    "ket qua xet nghiem",
    "chi so xet nghiem",
    "xet nghiem mau",
    "men gan",
    "ast",
    "alt",
    "creatinin",
    "creatinine",
    "hba1c",
    "cholesterol",
    "triglycerid",
    "triglyceride",
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
)

_MONITORING_MARKERS = ("spo2", "huyet ap", "nhip tim", "nhiet do", "duong huyet")
_FOLLOWUP_MARKERS = ("tai kham", "lich kham", "follow up", "follow-up", "lich hen")


def _contains_marker(norm: str, marker: str) -> bool:
    """Match task markers as lexical units, never arbitrary substrings."""
    return re.search(
        rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])",
        norm,
    ) is not None


def _is_peripheral_joint_request(norm: str) -> bool:
    """Detect a peripheral hand/wrist/finger joint complaint by semantics.

    V27 intentionally requires both a joint body-site signal and a symptom
    signal. Word order is flexible ("đau khớp ngón tay" and "khớp ngón tay
    ... đau" both match), while vague phrases such as "đau tay" do not.
    """
    joint_site = bool(
        re.search(
            r"\b(?:cac\s+|nhieu\s+)?khop\s+(?:ngon\s+tay|co\s+tay|ban\s+tay|tay)\b",
            norm,
        )
    )
    if not joint_site:
        return False
    symptom = bool(
        re.search(
            r"\b(?:dau|nhuc|sung|nong|do|cung|han che cu dong|kho cu dong|kho nam|kho cam)\b",
            norm,
        )
    )
    return symptom


def resolve_clinical_task(text: str) -> ClinicalTaskDecision:
    """Classify the *kind of clinical work* requested by the user.

    This router intentionally does not determine urgency. Safety/triage remain
    independent and may raise the care level later without changing the task.
    """
    norm = normalize_search_text(text)

    lab_hits = [marker for marker in _LAB_MARKERS if _contains_marker(norm, marker)]
    qualitative_result = bool(
        re.search(r"\b[a-z][a-z0-9-]{1,20}\s*(?:am tinh|duong tinh|\(-\)|\(\+\))", norm)
    )
    if lab_hits or qualitative_result:
        return ClinicalTaskDecision(
            task=ClinicalTask.LAB_INTERPRETATION,
            confidence=0.98 if lab_hits else 0.88,
            reasons=["laboratory_result_language_detected"],
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

    if any(_contains_marker(norm, marker) for marker in _MEDICATION_MARKERS):
        return ClinicalTaskDecision(
            task=ClinicalTask.MEDICATION_SAFETY,
            confidence=0.92,
            reasons=["medication_safety_request"],
            domain="medication",
        )

    if _is_peripheral_joint_request(norm):
        return ClinicalTaskDecision(
            task=ClinicalTask.PERIPHERAL_JOINT,
            confidence=0.94,
            reasons=["peripheral_joint_language_detected"],
            domain="peripheral_joint",
        )

    if any(_contains_marker(norm, marker) for marker in _MONITORING_MARKERS) and bool(
        re.search(r"\d", norm)
    ):
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
        )
    ):
        return ClinicalTaskDecision(
            task=ClinicalTask.ACUTE_SYMPTOM,
            confidence=0.78,
            reasons=["symptom_language_detected"],
            domain="clinical_symptom",
        )

    return ClinicalTaskDecision(
        task=ClinicalTask.GENERAL_MEDICAL,
        confidence=0.55,
        reasons=["no_specific_clinical_task_signal"],
        domain="general",
    )
