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
    "xem card",
    "hien thi card",
    "doi gio",
    "cap nhat gio",
    "sua gio",
    "xoa card",
    "huy card",
    "lich uong thuoc",
    "nhac uong",
    "hen gio uong",
    "fhir",
    "ocr",
    "webhook",
    "hang doi",
    "dat lich kham",
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

_SAFETY_DIRECT_MARKERS = (
    "tu doi lieu",
    "tu dieu chinh lieu",
    "tu bo lieu",
    "bo lieu thuoc",
    "lieu chinh xac",
    "lieu cu the",
    "nua lieu thuoc",
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
    "thuoc ngu",
    "thuoc chong dong",
    "thuoc huyet ap",
    "thuc pham bo sung",
    "thuoc cam",
)

_SAFETY_CONTINUATION_MARKERS = (
    "aspirin",
    "ibuprofen",
    "warfarin",
    "naproxen",
    "paracetamol",
    "metformin",
    "thuoc ngu",
    "thuoc chong dong",
    "lieu",
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


def _user_texts(messages: list[tuple[str, str]]) -> list[str]:
    return [content.strip() for role, content in messages if role == "user" and content.strip()]


def _has_workflow_intent(latest: str) -> bool:
    return any(marker in latest for marker in _WORKFLOW_MARKERS)


def _prior_metric_domain(history: str) -> str | None:
    """Return the most recently established monitoring metric family."""
    # Search the most recent text first by relying on the caller joining turns
    # newest-to-oldest.
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
    # Newest first so a recent domain switch wins over an older episode.
    history = "\n".join(reversed(prior_users[-4:]))

    # Explicit medication self-management questions are safety workflow even
    # when a symptom word elsewhere would otherwise bias acute-triage scoring.
    if any(marker in latest for marker in _SAFETY_DIRECT_MARKERS):
        return ContinuationResolution("safety", "explicit_medication_self_management", 0.98)

    if "thuoc chong dong" in latest and any(marker in latest for marker in ("chay mau", "chay mau cam", "bo lieu")):
        return ContinuationResolution("safety", "anticoagulant_safety_context", 0.97)

    # Monitoring values often omit the metric label after the first turn:
    # "SpO2 95%" -> "đi lại thì 92%"; "HA 148/92" -> "đo lại 152/94".
    metric = _prior_metric_domain(history)
    if metric:
        canonical = _canonical_metric(latest, metric)
        if canonical:
            return ContinuationResolution(
                "monitoring",
                f"elliptical_{metric}_measurement",
                0.99,
                augmented_latest=canonical,
            )

    # Pregnancy is an episode-level condition.  Vaginal bleeding in a later
    # short turn must stay attached to the active pregnancy episode.
    if prior_users and any(marker in history for marker in _PREGNANCY_MARKERS):
        if any(marker in latest for marker in _PREGNANCY_BLEEDING_MARKERS):
            return ContinuationResolution("triage", "pregnancy_bleeding_continuation", 0.99)

    # A medication-safety conversation commonly receives a short follow-up
    # containing only a newly disclosed medicine, condition or label detail.
    if prior_users and any(marker in history for marker in _SAFETY_CONTEXT_MARKERS):
        if any(marker in latest for marker in _SAFETY_CONTINUATION_MARKERS):
            return ContinuationResolution("safety", "medication_safety_continuation", 0.94)

    # First-turn symptom phrases that are clinically meaningful but previously
    # fell through to general because they do not contain the older fallback
    # vocabulary.  This changes only intent ownership, never severity.
    if any(marker in latest for marker in _DIRECT_TRIAGE_MARKERS):
        return ContinuationResolution("triage", "direct_clinical_symptom", 0.93)

    return None
