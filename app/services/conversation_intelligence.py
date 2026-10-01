"""V27.2 bounded conversation intelligence for multi-turn clinical chat.

This module deliberately does *not* add another free-form LLM agent.  It is a
small deterministic control layer around the existing router so that:

* the latest user goal wins over stale history;
* triage history is scoped to the active symptom episode;
* medication facts survive across turns without dragging unrelated symptoms;
* domain results carry the current-turn context needed by patient-facing
  composers.

Safety Kernel decisions are never downgraded here.  The layer can isolate stale
context or add remembered facts, but it cannot lower urgency, remove red flags,
or author a diagnosis.
"""

from __future__ import annotations

import re
from types import ModuleType
from typing import Any

from app.services.clinical_text import normalize_search_text
from app.services.risk_memory import infer_episode_domain, is_explicit_correction


_MARKER = "_medguard_v27_2_conversation_intelligence"

_ACUTE_SYMPTOM_MARKERS = (
    "dau nguc",
    "tuc nguc",
    "nang nguc",
    "kho tho",
    "hut hoi",
    "meo mieng",
    "noi ngong",
    "yeu tay",
    "yeu chan",
    "yeu liet",
    "ngat",
    "co giat",
    "dau dau du doi",
    "dau bung du doi",
    "chay mau",
)

_MEDICATION_SAFETY_MARKERS = (
    "uong duoc khong",
    "dung duoc khong",
    "co uong duoc",
    "co dung duoc",
    "uong chung",
    "uong cung",
    "uong kem",
    "dung chung",
    "dung kem",
    "uong them",
    "dung them",
    "tuong tac",
    "an toan thuoc",
    "tac dung phu",
    "qua lieu",
    "chua uong",
    "chua dung",
)

_CURRENT_MEDICATION_MARKERS = (
    "dang dung",
    "dang uong",
    "hien dung",
    "thuoc hien tai",
    "uong moi ngay",
    "dung moi ngay",
    "con dang uong",
    "con dang dung",
)

_PROPOSED_MEDICATION_MARKERS = (
    "co dung",
    "co uong",
    "uong them",
    "dung them",
    "muon dung",
    "muon uong",
    "can nhac",
    "du dinh",
)


def _latest_user_text(payload: Any) -> str:
    messages = getattr(payload, "messages", ()) or ()
    for message in reversed(messages):
        if getattr(message, "role", None) == "user":
            value = str(getattr(message, "content", "") or "").strip()
            if value:
                return value
    return ""


def _prior_user_texts(payload: Any) -> list[str]:
    messages = getattr(payload, "messages", ()) or ()
    result: list[str] = []
    for message in messages[:-1]:
        if getattr(message, "role", None) != "user":
            continue
        value = str(getattr(message, "content", "") or "").strip()
        if value:
            result.append(value)
    return result


def _has_acute_symptom(text: str) -> bool:
    normalized = normalize_search_text(text)
    return any(marker in normalized for marker in _ACUTE_SYMPTOM_MARKERS)


def _looks_like_monitoring_turn(chat_module: ModuleType, text: str) -> bool:
    """True for a measurement-focused turn, not a symptom+measurement crisis."""
    normalized = normalize_search_text(text)
    try:
        points = list(chat_module._extract_monitoring(text))
    except Exception:
        points = []
    if not points:
        return False
    # A value accompanied by acute symptom language belongs to clinical triage;
    # a value by itself belongs to monitoring and must not inherit stale triage.
    return not _has_acute_symptom(normalized)


def _looks_like_medication_turn(chat_module: ModuleType, text: str) -> bool:
    normalized = normalize_search_text(text)
    try:
        occurrences = list(chat_module._medication_occurrences(normalized))
    except Exception:
        occurrences = []
    if not occurrences:
        return False
    return any(marker in normalized for marker in _MEDICATION_SAFETY_MARKERS + _CURRENT_MEDICATION_MARKERS)


def _conversation_scope(chat_module: ModuleType, text: str) -> str:
    normalized = normalize_search_text(text)
    if getattr(chat_module, "is_schedule_chat_command", lambda value: False)(normalized):
        return "schedule"
    if _looks_like_monitoring_turn(chat_module, text):
        return "monitoring"
    if _looks_like_medication_turn(chat_module, text):
        return "medication_safety"
    domain = infer_episode_domain(text)
    if domain:
        return f"triage:{domain}"
    return "continuation"


def _scoped_triage_history(chat_module: ModuleType, payload: Any, latest_text: str) -> tuple[str, bool, bool]:
    """Build triage context from the active complaint only.

    The previous implementation appended the last three user turns even when the
    conversation had moved through medication safety or monitoring.  This
    function walks backwards until it reaches a different explicit complaint.
    """
    if is_explicit_correction(latest_text):
        return latest_text, False, False

    latest_domain = infer_episode_domain(latest_text)
    if not latest_domain:
        # Continuation messages such as "đỡ hơn rồi" need the base selector's
        # risk-memory semantics because the complaint may be implicit.
        return chat_module._v27_2_original_triage_episode_text(payload, latest_text)

    previous = _prior_user_texts(payload)
    relevant: list[str] = []
    switched = False

    for value in reversed(previous):
        scope = _conversation_scope(chat_module, value)
        if scope in {"monitoring", "medication_safety", "schedule"}:
            # Non-triage tasks are transparent boundaries: skip them rather than
            # feeding them into the clinical episode.
            continue
        domain = infer_episode_domain(value)
        if domain is None:
            # A short continuation can belong to the active episode only after a
            # same-domain anchor has already been found.
            if relevant:
                relevant.append(value)
            continue
        if domain != latest_domain:
            switched = True
            break
        relevant.append(value)
        if len(relevant) >= 3:
            break

    relevant.reverse()
    if not relevant:
        return latest_text, False, switched

    candidate = "\n".join([*relevant, f"Lượt hiện tại: {latest_text}"])
    selection = chat_module.select_active_episode_text(candidate)
    return selection.text, True, bool(switched or selection.switched_episode)


def _classify_medications(chat_module: ModuleType, text: str) -> tuple[list[str], list[str]]:
    normalized = normalize_search_text(text)
    try:
        meds = [name for _, name in chat_module._medication_occurrences(normalized)]
    except Exception:
        meds = []
    meds = list(dict.fromkeys(meds))
    if not meds:
        return [], []

    current: list[str] = []
    proposed: list[str] = []
    has_current = any(marker in normalized for marker in _CURRENT_MEDICATION_MARKERS)
    has_proposed = any(marker in normalized for marker in _PROPOSED_MEDICATION_MARKERS)

    if has_current and has_proposed and len(meds) >= 2:
        current.append(meds[0])
        proposed.extend(meds[1:])
    elif has_current:
        current.extend(meds)
    elif has_proposed or any(marker in normalized for marker in _MEDICATION_SAFETY_MARKERS):
        proposed.extend(meds)
    return current, proposed


def _collect_medication_memory(chat_module: ModuleType, payload: Any) -> tuple[list[str], list[str]]:
    """Return remembered current and pending/proposed medicines.

    Current medicines are longitudinal patient context.  A pending medicine is
    retained only from the most recent medication-safety turn so a later
    follow-up such as "nếu tôi chưa uống ibuprofen" does not ask for the name
    again.
    """
    current: list[str] = []
    latest_proposed: list[str] = []
    for value in _prior_user_texts(payload):
        turn_current, turn_proposed = _classify_medications(chat_module, value)
        for med in turn_current:
            if med not in current:
                current.append(med)
        if turn_proposed:
            latest_proposed = list(dict.fromkeys(turn_proposed))
    return current, latest_proposed


def _augment_safety_context(chat_module: ModuleType, payload: Any, normalized_text: str):
    original = chat_module._v27_2_original_extract_safety
    current, proposed, allergens, conditions = original(payload, normalized_text)
    remembered_current, remembered_proposed = _collect_medication_memory(chat_module, payload)

    latest_text = _latest_user_text(payload)
    latest_current, latest_proposed = _classify_medications(chat_module, latest_text)

    # Longitudinal current medicines survive task switches.
    for med in [*remembered_current, *latest_current]:
        if med not in current:
            current.append(med)

    # If the latest turn establishes a new "currently taking" medicine but does
    # not replace the pending candidate, preserve the candidate from the prior
    # safety turn.  This covers warfarin -> ibuprofen -> aspirin follow-ups.
    if not proposed and remembered_proposed:
        normalized_latest = normalize_search_text(latest_text)
        continuation = (
            any(med in normalized_latest for med in remembered_proposed)
            or "thuoc do" in normalized_latest
            or "thuoc nay" in normalized_latest
            or any(marker in normalized_latest for marker in ("chua uong", "chua dung", "neu toi"))
            or bool(latest_current and not latest_proposed)
        )
        if continuation:
            proposed.extend(remembered_proposed)

    return (
        list(dict.fromkeys(current)),
        list(dict.fromkeys(proposed)),
        list(dict.fromkeys(allergens)),
        list(dict.fromkeys(conditions)),
    )


def _enrich_result(chat_module: ModuleType, payload: Any, intent: str, result: Any) -> Any:
    """Attach presentation-only context to the structured result.

    These fields are ignored by Safety Kernel logic and exist solely so the
    response composer can describe *this* turn rather than a generic template.
    """
    if result is None:
        return result
    if hasattr(result, "model_dump"):
        data = result.model_dump(mode="json")
    elif isinstance(result, dict):
        data = dict(result)
    else:
        return result

    latest = _latest_user_text(payload)
    data["conversation_turn"] = latest
    data["conversation_scope"] = _conversation_scope(chat_module, latest)

    if intent == "monitoring":
        try:
            data["patient_measurements"] = [
                {
                    "metric": point.metric,
                    "value": point.value,
                    "unit": point.unit,
                }
                for point in chat_module._extract_monitoring(latest)
            ]
        except Exception:
            data["patient_measurements"] = []

    if intent == "safety":
        remembered_current, remembered_proposed = _collect_medication_memory(chat_module, payload)
        latest_current, latest_proposed = _classify_medications(chat_module, latest)
        data["conversation_current_medications"] = list(
            dict.fromkeys([*remembered_current, *latest_current])
        )
        data["conversation_proposed_medications"] = list(
            dict.fromkeys(latest_proposed or remembered_proposed)
        )

    return data


def install_chat_conversation_intelligence(chat_module: ModuleType) -> None:
    if getattr(chat_module, _MARKER, False):
        return

    original_detect = getattr(chat_module, "_detect_intent", None)
    original_episode = getattr(chat_module, "_triage_episode_text", None)
    original_safety = getattr(chat_module, "_extract_safety", None)
    original_response = getattr(chat_module, "_response", None)
    if not all((original_detect, original_episode, original_safety, original_response)):
        return

    chat_module._v27_2_original_detect_intent = original_detect
    chat_module._v27_2_original_triage_episode_text = original_episode
    chat_module._v27_2_original_extract_safety = original_safety
    chat_module._v27_2_original_response = original_response

    def _detect_intent(payload: Any, normalized_text: str):
        if getattr(payload, "intent_hint", "auto") != "auto":
            return original_detect(payload, normalized_text)
        latest = _latest_user_text(payload)
        if _looks_like_monitoring_turn(chat_module, latest):
            return "monitoring"
        if _looks_like_medication_turn(chat_module, latest):
            return "safety"
        return original_detect(payload, normalized_text)

    def _triage_episode_text(payload: Any, latest_text: str):
        return _scoped_triage_history(chat_module, payload, latest_text)

    def _extract_safety(payload: Any, normalized_text: str):
        return _augment_safety_context(chat_module, payload, normalized_text)

    def _response(payload: Any, ctx: Any, **kwargs: Any):
        intent = str(kwargs.get("intent") or "general")
        kwargs["result"] = _enrich_result(chat_module, payload, intent, kwargs.get("result"))
        return original_response(payload, ctx, **kwargs)

    chat_module._detect_intent = _detect_intent
    chat_module._triage_episode_text = _triage_episode_text
    chat_module._extract_safety = _extract_safety
    chat_module._response = _response
    setattr(chat_module, _MARKER, True)
