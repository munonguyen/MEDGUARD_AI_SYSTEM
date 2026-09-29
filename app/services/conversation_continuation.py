"""Resolve elliptical multi-turn continuations before the normal intent router.

The resolver is deliberately conservative.  It does not diagnose or assign
clinical severity.  Its only authority is to recover an already-established
conversation domain and, for vital-sign continuations, create a canonical
routing/extraction view of the latest measurement.

The original user message is retained separately by ``ChatRequest`` and remains
the value written to durable chat history.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from app.knowledge.loader import knowledge
from app.services.clinical_text import normalize_search_text


ContinuationIntent = Literal["triage", "safety", "monitoring"]


@dataclass(frozen=True)
class ContinuationResolution:
    intent: ContinuationIntent
    reason: str
    confidence: float
    augmented_latest: str | None = None


_WORKFLOW_MARKERS = (
    "#lichthuoc",
    "tao card",
    "tao cho toi mot card",
    "xem card",
    "xem lai card",
    "hien thi card",
    "card lich",
    "card nhac",
    "doi gio",
    "cap nhat gio",
    "sua gio",
    "chuyen gio",
    "xoa card",
    "huy card",
    "tam dung card",
    "ngung card",
    "xoa lich uong",
    "xoa lich nhac",
    "huy lich uong",
    "huy lich nhac",
    "tam dung lich",
    "ngung lich",
    "lich uong thuoc",
    "lich nhac",
    "nhac uong",
    "hen gio uong",
    "fhir",
    "ocr",
    "webhook",
    "hang doi",
    "dat lich kham",
)

_EXPLICIT_CONTEXT_SWITCH_MARKERS = (
    "chuyen viec khac",
    "chuyen sang viec khac",
    "van de moi",
    "chuyen sang van de khac",
)

_PREGNANCY_MARKERS = (
    "mang thai",
    "co thai",
    "thai 8 tuan",
    "thai khoang 8 tuan",
    "thai som",
    "3 thang dau",
)
_PREGNANCY_BLEEDING_MARKERS = (
    "ra mau am dao",
    "chay mau am dao",
    "mau am dao",
)

_DIRECT_TRIAGE_MARKERS = (
    "me day",
    "noi me day",
    "nuoc nong ban",
    "bong nuoc",
    "dao cat",
    "vet cat",
    "vet rach",
    "mat trai do",
    "mat phai do",
    "mat do",
    "co mat",
    "kho khe",
)

_HIGH_RISK_CIRCULATORY_MARKERS = (
    "gan ngat",
    "sap ngat",
    "muon ngat",
    "muon xiu",
    "ngat xiu",
    "bat tinh",
)

_RESPIRATORY_EPISODE_MARKERS = (
    "kho tho",
    "hut hoi",
    "tho nhanh",
    "tho gap",
    "ho",
    "sot",
    "dau hong",
)

_SAFETY_DIRECT_MARKERS = (
    "tu doi lieu",
    "tu dieu chinh lieu",
    "tu bo lieu",
    "bo lieu thuoc",
    "lieu chinh xac",
    "lieu cu the",
    "nua lieu thuoc",
    "nua vien",
    "thu nua",
    "tu gay non",
    "gay non de",
    "dung chung an toan",
    "uong chung an toan",
    "co an toan hon",
)

_SAFETY_CONTEXT_MARKERS = (
    "warfarin",
    "aspirin",
    "ibuprofen",
    "naproxen",
    "paracetamol",
    "acetaminophen",
    "metformin",
    "amoxicillin",
    "penicillin",
    "thuoc ngu",
    "thuoc chong dong",
    "thuoc huyet ap",
    "thuc pham bo sung",
    "thuoc cam",
    "uong nham",
    "gap doi thuoc",
    "qua lieu",
    "thuoc cua minh",
)

_SAFETY_CONTINUATION_MARKERS = (
    "aspirin",
    "ibuprofen",
    "warfarin",
    "naproxen",
    "paracetamol",
    "metformin",
    "amoxicillin",
    "penicillin",
    "thuoc ngu",
    "thuoc chong dong",
    "lieu",
    "nua vien",
    "thu nua",
    "tu gay non",
    "gay non",
    "day thuoc ra",
    "nhan",
    "thanh phan",
    "hon hop thao duoc",
    "viem loet da day",
    "loet da day",
    "dung chung",
    "uong them",
    "bo lieu",
    "doi lieu",
)

_EYE_COMPLAINT = re.compile(
    r"(?:\bmat\b(?:\s+[a-z0-9]+){0,6}\s+\b(?:do|com|dau|nhuc|mo|sung|ngua|chay nuoc mat)\b"
    r"|\b(?:do|com|dau|nhuc|mo|sung|ngua)\b(?:\s+[a-z0-9]+){0,6}\s+\bmat\b)"
)


def _user_texts(messages: list[tuple[str, str]]) -> list[str]:
    return [content.strip() for role, content in messages if role == "user" and content.strip()]


def _has_workflow_intent(latest: str) -> bool:
    """Protect explicit workflow commands from clinical continuation recovery."""
    if any(marker in latest for marker in _WORKFLOW_MARKERS):
        return True
    return bool(
        "card" in latest
        and any(word in latest for word in ("uong", "thuoc", "nhac", "gio", "lich"))
    )


def _is_explicit_medication_safety_request(latest: str) -> bool:
    """Identify a new medication-use question without relying on prior symptoms."""
    medication_context = any(marker in latest for marker in _SAFETY_CONTEXT_MARKERS) or "thuoc" in latest
    use_question = any(
        marker in latest
        for marker in (
            "dung duoc khong",
            "uong duoc khong",
            "co dung",
            "co uong",
            "dung chung",
            "uong chung",
            "an toan",
            "tuong tac",
            "lieu",
            "them",
        )
    )
    return medication_context and use_question


def _prior_metric_domain(history: str) -> str | None:
    """Return the most recently established monitoring metric family."""
    if "spo2" in history or "do bao hoa oxy" in history:
        return "spo2"
    if "huyet ap" in history or re.search(r"\b\d{2,3}\s*/\s*\d{2,3}\s*mmhg\b", history):
        return "blood_pressure"
    if "nhip tim" in history or "mach" in history or "lan/phut" in history or "bpm" in history:
        return "heart_rate"
    if "nhiet do" in history or re.search(r"\b(?:3[5-9]|4[0-3])(?:[.,]\d+)?\s*(?:do c|°c)\b", history):
        return "temperature"
    if "duong huyet" in history or "glucose" in history:
        return "glucose"
    return None


def _monitoring_rule(metric: str) -> dict | None:
    for rule in knowledge.monitoring_rules:
        if str(rule.get("metric")) == metric:
            return rule
    return None


def _numeric_percentage(text: str) -> float | None:
    match = re.search(r"\b(\d{2,3}(?:[.,]\d+)?)\s*%", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def _spo2_stays_in_acute_episode(*, history: str, latest: str) -> bool:
    """Keep severe hypoxia follow-ups inside the acute triage episode."""
    rule = _monitoring_rule("spo2")
    critical_below = rule.get("critical_below") if rule else None
    if not isinstance(critical_below, (int, float)):
        return False

    latest_value = _numeric_percentage(latest)
    if latest_value is None or latest_value >= float(critical_below):
        return False

    prior_values = [
        float(value.replace(",", "."))
        for value in re.findall(r"\b(\d{2,3}(?:[.,]\d+)?)\s*%", history)
    ]
    prior_critical = any(value < float(critical_below) for value in prior_values)
    respiratory_context = any(marker in history for marker in _RESPIRATORY_EPISODE_MARKERS)
    return prior_critical and respiratory_context


def _canonical_metric(latest: str, metric: str) -> str | None:
    if metric == "blood_pressure":
        match = re.search(r"\b(\d{2,3})\s*/\s*(\d{2,3})\b", latest)
        if match:
            return f"Huyết áp {match.group(1)}/{match.group(2)} mmHg. {latest}"
    elif metric == "spo2":
        match = re.search(r"\b(\d{2,3}(?:[.,]\d+)?)\s*%", latest)
        if match:
            return f"SpO2 {match.group(1).replace(',', '.')}%. {latest}"
    elif metric == "heart_rate":
        match = re.search(r"\b(\d{2,3}(?:[.,]\d+)?)\s*(?:lan\s*/?\s*phut|bpm)\b", latest)
        if match:
            return f"Nhịp tim {match.group(1).replace(',', '.')} bpm. {latest}"
    elif metric == "temperature":
        match = re.search(r"\b((?:3[5-9]|4[0-3])(?:[.,]\d+)?)\s*(?:do\s*c|°c|c)?\b", latest)
        if match:
            return f"Nhiệt độ {match.group(1).replace(',', '.')} C. {latest}"
    elif metric == "glucose":
        match = re.search(r"\b(\d{2,4}(?:[.,]\d+)?)\s*(mg\s*/?\s*dl|mmol\s*/?\s*l)\b", latest)
        if match:
            unit = "mg/dL" if "mg" in match.group(2) else "mmol/L"
            return f"Đường huyết {match.group(1).replace(',', '.')} {unit}. {latest}"
    return None


def resolve_conversation_continuation(
    messages: list[tuple[str, str]],
) -> ContinuationResolution | None:
    """Recover a high-confidence clinical domain from cumulative chat context."""
    users = _user_texts(messages)
    if not users:
        return None

    latest_raw = users[-1]
    latest = normalize_search_text(latest_raw)
    if _has_workflow_intent(latest):
        return None

    prior_users = [normalize_search_text(value) for value in users[:-1]]
    history = "\n".join(reversed(prior_users[-4:]))

    # A user explicitly switching topics should not inherit a prior clinical
    # episode.  When the new topic is clearly medication use, assign ownership
    # directly to safety and let the safety service determine the actual risk.
    if any(marker in latest for marker in _EXPLICIT_CONTEXT_SWITCH_MARKERS):
        if _is_explicit_medication_safety_request(latest):
            return ContinuationResolution("safety", "explicit_new_medication_topic", 0.995)
        return None

    if any(marker in latest for marker in _SAFETY_DIRECT_MARKERS):
        return ContinuationResolution("safety", "explicit_medication_self_management", 0.98)

    if "thuoc chong dong" in latest and any(marker in latest for marker in ("chay mau", "chay mau cam", "bo lieu")):
        return ContinuationResolution("safety", "anticoagulant_safety_context", 0.97)

    metric = _prior_metric_domain(history)

    if metric == "heart_rate" and any(marker in latest for marker in _HIGH_RISK_CIRCULATORY_MARKERS):
        return ContinuationResolution(
            "triage",
            "heart_rate_with_presyncope",
            0.995,
        )

    if metric == "spo2" and _spo2_stays_in_acute_episode(history=history, latest=latest):
        return ContinuationResolution(
            "triage",
            "persistent_critical_spo2_in_acute_respiratory_episode",
            0.995,
            augmented_latest=_canonical_metric(latest, metric),
        )

    if metric:
        canonical = _canonical_metric(latest, metric)
        if canonical:
            return ContinuationResolution(
                "monitoring",
                f"elliptical_{metric}_measurement",
                0.99,
                augmented_latest=canonical,
            )

    if prior_users and any(marker in history for marker in _PREGNANCY_MARKERS):
        if any(marker in latest for marker in _PREGNANCY_BLEEDING_MARKERS):
            return ContinuationResolution("triage", "pregnancy_bleeding_continuation", 0.99)

    if prior_users and any(marker in history for marker in _SAFETY_CONTEXT_MARKERS):
        if any(marker in latest for marker in _SAFETY_CONTINUATION_MARKERS):
            return ContinuationResolution("safety", "medication_safety_continuation", 0.96)

    if _EYE_COMPLAINT.search(latest):
        return ContinuationResolution("triage", "direct_eye_complaint", 0.97)

    if any(marker in latest for marker in _DIRECT_TRIAGE_MARKERS):
        return ContinuationResolution("triage", "direct_clinical_symptom", 0.93)

    return None
