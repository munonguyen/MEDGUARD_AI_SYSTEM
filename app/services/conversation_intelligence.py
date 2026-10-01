"""V27.2 bounded conversation intelligence for multi-turn clinical chat.

Deterministic control layer around the existing router. It scopes history,
remembers medication facts and enriches structured results without lowering
Safety Kernel decisions or adding an unrestricted response author.
"""

from __future__ import annotations

import re
from types import ModuleType
from typing import Any

from app.core.config import settings
from app.services.clinical_text import normalize_search_text
from app.services.risk_memory import infer_episode_domain, is_explicit_correction


_MARKER = "_medguard_v27_2_conversation_intelligence"

_ACUTE_SYMPTOM_MARKERS = (
    "dau nguc", "tuc nguc", "nang nguc", "kho tho", "hut hoi", "meo mieng", "noi ngong",
    "yeu tay", "yeu chan", "yeu liet", "ngat", "co giat", "dau dau du doi", "dau bung",
    "dau bung du doi", "buon non", "non", "chay mau", "sot", "sot cao", "lu du", "lo mo",
    "lanh run", "on lanh", "co cung", "te", "sung", "phat ban",
)

_CONTINUATION_MARKERS = (
    "cam giac no", "con dau", "van con", "van bi", "do hon", "bot hon", "bot mot chut",
    "nang hon", "dau tang", "buon non", "nong rat", "o chua", "khi doi", "sau an", "luc doi",
    "them nua", "sung moi", "co hong", "nghen hong", "hong van", "van kho chiu",
)

_MEDICATION_SAFETY_MARKERS = (
    "uong duoc khong", "dung duoc khong", "co uong duoc", "co dung duoc", "uong chung", "uong cung",
    "uong kem", "dung chung", "dung kem", "uong them", "dung them", "tuong tac", "an toan thuoc",
    "tac dung phu", "qua lieu", "chua uong", "chua dung",
)

_CURRENT_MEDICATION_MARKERS = (
    "dang dung", "dang uong", "hien dung", "thuoc hien tai", "uong moi ngay", "dung moi ngay",
    "con dang uong", "con dang dung",
)

_PROPOSED_MEDICATION_MARKERS = (
    "co dung", "co uong", "uong them", "dung them", "muon dung", "muon uong", "can nhac", "du dinh",
)


def _latest_user_text(payload: Any) -> str:
    for message in reversed(getattr(payload, "messages", ()) or ()):
        if getattr(message, "role", None) == "user":
            value = str(getattr(message, "content", "") or "").strip()
            if value:
                return value
    return ""


def _prior_user_texts(payload: Any) -> list[str]:
    result: list[str] = []
    for message in (getattr(payload, "messages", ()) or ())[:-1]:
        if getattr(message, "role", None) == "user":
            value = str(getattr(message, "content", "") or "").strip()
            if value:
                result.append(value)
    return result


def _has_acute_symptom(text: str) -> bool:
    normalized = normalize_search_text(text)
    return infer_episode_domain(text) is not None or any(marker in normalized for marker in _ACUTE_SYMPTOM_MARKERS)


def _looks_like_monitoring_turn(chat_module: ModuleType, text: str) -> bool:
    try:
        points = list(chat_module._extract_monitoring(text))
    except Exception:
        points = []
    return bool(points) and not _has_acute_symptom(text)


def _looks_like_medication_turn(chat_module: ModuleType, text: str) -> bool:
    normalized = normalize_search_text(text)
    try:
        occurrences = list(chat_module._medication_occurrences(normalized))
    except Exception:
        occurrences = []
    return bool(occurrences) and any(
        marker in normalized for marker in _MEDICATION_SAFETY_MARKERS + _CURRENT_MEDICATION_MARKERS
    )


def _conversation_scope(chat_module: ModuleType, text: str) -> str:
    normalized = normalize_search_text(text)
    if getattr(chat_module, "is_schedule_chat_command", lambda value: False)(normalized):
        return "schedule"
    if _looks_like_monitoring_turn(chat_module, text):
        return "monitoring"
    if _looks_like_medication_turn(chat_module, text):
        return "medication_safety"
    domain = infer_episode_domain(text)
    return f"triage:{domain}" if domain else "continuation"


def _scoped_triage_history(chat_module: ModuleType, payload: Any, latest_text: str) -> tuple[str, bool, bool]:
    if is_explicit_correction(latest_text):
        return latest_text, False, False

    normalized_latest = normalize_search_text(latest_text)
    previous = _prior_user_texts(payload)
    if previous and any(marker in normalized_latest for marker in _CONTINUATION_MARKERS):
        return chat_module._v27_2_original_triage_episode_text(payload, latest_text)

    latest_domain = infer_episode_domain(latest_text)
    if not latest_domain:
        return chat_module._v27_2_original_triage_episode_text(payload, latest_text)

    relevant: list[str] = []
    switched = False
    for value in reversed(previous):
        scope = _conversation_scope(chat_module, value)
        if scope in {"monitoring", "medication_safety", "schedule"}:
            continue
        domain = infer_episode_domain(value)
        if domain is None:
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
    if has_current and has_proposed:
        if len(meds) >= 2:
            current.append(meds[0])
            proposed.extend(meds[1:])
        else:
            # One active ingredient may occur on both sides of a duplicate-
            # ingredient question (for example paracetamol in two products).
            current.extend(meds)
            proposed.extend(meds)
    elif has_current:
        current.extend(meds)
    elif has_proposed or any(marker in normalized for marker in _MEDICATION_SAFETY_MARKERS):
        proposed.extend(meds)
    return current, proposed


def _collect_medication_memory(chat_module: ModuleType, payload: Any) -> tuple[list[str], list[str]]:
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
    current, proposed, allergens, conditions = chat_module._v27_2_original_extract_safety(payload, normalized_text)
    remembered_current, remembered_proposed = _collect_medication_memory(chat_module, payload)
    latest_text = _latest_user_text(payload)
    latest_current, latest_proposed = _classify_medications(chat_module, latest_text)

    for med in [*remembered_current, *latest_current]:
        if med not in current:
            current.append(med)
    # Merge current-turn classification as well as historical memory. The base
    # parser intentionally accepts a narrower grammar than conversation turns.
    for med in latest_proposed:
        if med not in proposed:
            proposed.append(med)
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
        list(dict.fromkeys(current)), list(dict.fromkeys(proposed)),
        list(dict.fromkeys(allergens)), list(dict.fromkeys(conditions)),
    )


def _natural_monitoring_alias_text(text: str) -> str:
    """Convert natural Vietnamese measurement sentences to parser aliases.

    The mature monitoring parser intentionally uses strict token/value forms.
    V27.2 accepts common patient phrasing while still bounding the distance from
    a metric label to its numeric value, then delegates validation/ranges back to
    that existing parser rather than creating a second threshold engine.
    """
    normalized = normalize_search_text(text).replace(",", ".")
    aliases: list[str] = []
    patterns = (
        ("spo2", r"\bspo2\b[^\d\n]{0,40}?(\d{1,3}(?:\.\d+)?)", "%"),
        ("nhip tim", r"\b(?:nhip tim|mach)\b[^\d\n]{0,40}?(\d{2,3}(?:\.\d+)?)", ""),
        ("nhiet do", r"\b(?:nhiet do|sot)\b[^\d\n]{0,40}?(\d{2}(?:\.\d+)?)", ""),
        ("duong huyet", r"\b(?:duong huyet|glucose)\b[^\d\n]{0,40}?(\d{2,4}(?:\.\d+)?)", ""),
        ("muc dau", r"\b(?:muc dau|dau)\b[^\d\n]{0,40}?(\d{1,2}(?:\.\d+)?)\s*/\s*10", "/10"),
    )
    for label, pattern, suffix in patterns:
        match = re.search(pattern, normalized)
        if match:
            aliases.append(f"{label} {match.group(1)}{suffix}")
    pressure = re.search(r"\b(?:huyet ap|ha)\b[^\d\n]{0,40}?(\d{2,3})\s*/\s*(\d{2,3})", normalized)
    if pressure:
        aliases.append(f"huyet ap {pressure.group(1)}/{pressure.group(2)}")
    return " ".join(aliases)


def _enrich_result(chat_module: ModuleType, payload: Any, intent: str, result: Any) -> Any:
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
    data["conversation_turn_index"] = sum(
        1 for message in (getattr(payload, "messages", ()) or ()) if getattr(message, "role", None) == "user"
    )
    data["conversation_scope"] = _conversation_scope(chat_module, latest)

    if intent == "monitoring":
        try:
            data["patient_measurements"] = [
                {"metric": point.metric, "value": point.value, "unit": point.unit}
                for point in chat_module._extract_monitoring(latest)
            ]
        except Exception:
            data["patient_measurements"] = []

    if intent == "safety":
        remembered_current, remembered_proposed = _collect_medication_memory(chat_module, payload)
        latest_current, latest_proposed = _classify_medications(chat_module, latest)
        data["conversation_current_medications"] = list(dict.fromkeys([*remembered_current, *latest_current]))
        data["conversation_proposed_medications"] = list(dict.fromkeys(latest_proposed or remembered_proposed))
    return data


def install_chat_conversation_intelligence(chat_module: ModuleType) -> None:
    if getattr(chat_module, _MARKER, False):
        return
    original_detect = getattr(chat_module, "_detect_intent", None)
    original_episode = getattr(chat_module, "_triage_episode_text", None)
    original_safety = getattr(chat_module, "_extract_safety", None)
    original_monitoring = getattr(chat_module, "_extract_monitoring", None)
    original_response = getattr(chat_module, "_response", None)
    if not all((original_detect, original_episode, original_safety, original_monitoring, original_response)):
        return

    chat_module._v27_2_original_detect_intent = original_detect
    chat_module._v27_2_original_triage_episode_text = original_episode
    chat_module._v27_2_original_extract_safety = original_safety
    chat_module._v27_2_original_extract_monitoring = original_monitoring
    chat_module._v27_2_original_response = original_response

    def _extract_monitoring(text: str):
        points = list(original_monitoring(text))
        alias_text = _natural_monitoring_alias_text(text)
        if alias_text:
            seen = {(point.metric, float(point.value)) for point in points}
            for point in original_monitoring(alias_text):
                key = (point.metric, float(point.value))
                if key not in seen:
                    points.append(point)
                    seen.add(key)
        return points

    # Install measurement parsing before intent classification so a natural
    # sentence such as "SpO2 của tôi lúc nghỉ là 95%" is routed to monitoring.
    chat_module._extract_monitoring = _extract_monitoring

    def _detect_intent(payload: Any, normalized_text: str):
        if getattr(payload, "intent_hint", "auto") != "auto":
            return original_detect(payload, normalized_text)
        latest = _latest_user_text(payload)
        if _looks_like_medication_turn(chat_module, latest):
            return "safety"
        if _looks_like_monitoring_turn(chat_module, latest):
            return "monitoring"
        return original_detect(payload, normalized_text)

    def _triage_episode_text(payload: Any, latest_text: str):
        return _scoped_triage_history(chat_module, payload, latest_text)

    def _extract_safety(payload: Any, normalized_text: str):
        return _augment_safety_context(chat_module, payload, normalized_text)

    def _response(payload: Any, ctx: Any, **kwargs: Any):
        # Preserve the V14 single-path invariant in this wrapper itself. In
        # coverage_scope=all, no branch may disable Writer/Reviewer by passing
        # allow_agent=False; the original response function rechecks this too.
        effective_allow_agent = bool(kwargs.get("allow_agent", True))
        if (
            settings.agent_coverage_scope == "all"
            and settings.agent_mode in {"shadow", "enforced"}
            and (settings.agent_sync_enabled or settings.agent_background_enabled)
        ):
            effective_allow_agent = True
        kwargs["allow_agent"] = effective_allow_agent

        intent = str(kwargs.get("intent") or "general")
        kwargs["result"] = _enrich_result(chat_module, payload, intent, kwargs.get("result"))
        return original_response(payload, ctx, **kwargs)

    chat_module._detect_intent = _detect_intent
    chat_module._triage_episode_text = _triage_episode_text
    chat_module._extract_safety = _extract_safety
    chat_module._response = _response
    setattr(chat_module, _MARKER, True)