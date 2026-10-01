"""V27.3 explanation-grounding hardening.

The V27.2 episode adapters intentionally preserve safety floors, but a few broad
lexical triggers could attach the wrong *explanation* to an otherwise correct
emergency decision. This final reasoner adapter removes only unsupported
mechanisms; it never lowers urgency or deletes Safety Kernel actions.
"""

from __future__ import annotations

import re
from types import ModuleType
from typing import Any

from app.services.clinical_text import normalize_search_text


_MARKER = "_medguard_v27_3_output_quality_reasoning"
_CHEST_DELTA_IDS = {
    "episode_delta_cardiorespiratory_warning",
    "historical_cardiorespiratory_emergency",
}
_NEURO_DELTA_IDS = {
    "episode_delta_neurologic_warning",
    "historical_neurologic_emergency",
}
_SPINE_DELTA_IDS = {
    "episode_delta_spinal_neurologic_warning",
    "historical_spinal_neurologic_emergency",
}


def _current_turn(episode: Any) -> str:
    raw = str(getattr(episode, "latest_user_message", "") or "").strip()
    lowered = raw.lower()
    marker = "lượt hiện tại:"
    if marker in lowered:
        return raw[lowered.rfind(marker) + len(marker):].strip()
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    return lines[-1] if lines else raw


def _episode_text(episode: Any) -> str:
    values = [
        str(getattr(episode, "active_episode_text", "") or ""),
        str(getattr(episode, "latest_user_message", "") or ""),
    ]
    for fact in tuple(getattr(episode, "confirmed_positive", ()) or ()):
        span = str(getattr(fact, "evidence_span", "") or "")
        if span:
            values.append(span)
    return " ".join(value for value in values if value)


def _has_mechanical_chest_baseline(text: str) -> bool:
    norm = normalize_search_text(text)
    chest = bool(re.search(r"\b(?:nguc|co nguc|thanh nguc|xuong suon|bo suon)\b", norm))
    load = bool(re.search(r"\b(?:sau tap|tap gym|tap nguc|nang ta|day nguc|hit dat|van dong manh)\b", norm))
    reproducible = bool(
        re.search(r"\b(?:an vao.*dau|dau khi an|so vao.*dau|xoay nguoi.*dau|co co.*dau)\b", norm)
    )
    return chest and load and reproducible


def _respiratory_speech_limitation(text: str) -> bool:
    norm = normalize_search_text(text)
    respiratory = bool(
        re.search(
            r"\b(?:hut hoi|kho tho|tho gap|tho doc|nghet tho|khong noi tron cau|"
            r"kho noi cau dai|noi cau dai.*hut hoi)\b",
            norm,
        )
    )
    strong_focal = bool(
        re.search(
            r"\b(?:noi ngong|meo mieng|lech mieng|yeu tay|yeu chan|yeu nua nguoi|"
            r"te nua nguoi|khong tim duoc tu|aphasia)\b",
            norm,
        )
    )
    return respiratory and not strong_focal


def _negated_spinal_deficit(text: str) -> bool:
    norm = normalize_search_text(text)
    return bool(
        re.search(
            r"\b(?:khong|chua|chang|ko|k)(?:\s+(?:co|bi|thay))?"
            r"(?:\s+(?:te|te ran)){0,2}\s+(?:yeu|liet)\s+(?:chan|tay)\b",
            norm,
        )
        or re.search(r"\b(?:khong|chua)(?:\s+co)?\s+te\s+vung\s+(?:yen ngua|quanh mong|hoi am)\b", norm)
        or re.search(r"\b(?:khong|chua)(?:\s+bi)?\s+(?:roi loan|mat|kho)\s+kiem soat\s+(?:tieu|dai)\s+tien\b", norm)
    )


def _drop_mechanisms(frame: Any, ids: set[str]) -> Any:
    original = list(tuple(getattr(frame, "mechanisms", ()) or ()))
    kept = [item for item in original if getattr(item, "hypothesis_id", "") not in ids]
    if len(kept) == len(original):
        return frame

    if kept and not any(getattr(item, "role", "") == "leading" for item in kept):
        first = kept[0]
        try:
            kept[0] = first.model_copy(update={"role": "leading"})
        except Exception:
            pass
    leading = tuple(
        getattr(item, "hypothesis_id", "")
        for item in kept
        if getattr(item, "role", "") == "leading" and getattr(item, "hypothesis_id", "")
    )
    return frame.model_copy(update={"mechanisms": tuple(kept), "leading_hypothesis_ids": leading})


def _clean_frame(frame: Any, episode: Any) -> Any:
    current = _current_turn(episode)
    full = _episode_text(episode)

    # The cardiorespiratory delta adapter is specifically a chest-wall anchoring
    # correction. Rash on the chest or chemical-inhalation chest tightness does
    # not provide a mechanical chest baseline and must not inherit that prose.
    if not _has_mechanical_chest_baseline(full):
        frame = _drop_mechanisms(frame, _CHEST_DELTA_IDS)

    # "Khó nói câu dài vì hụt hơi" is loss of respiratory reserve, not aphasia.
    if _respiratory_speech_limitation(current):
        frame = _drop_mechanisms(frame, _NEURO_DELTA_IDS)

    # A directly negated leg weakness/saddle/bladder finding must never be
    # rewritten as a newly present spinal neurologic deficit.
    if _negated_spinal_deficit(current):
        frame = _drop_mechanisms(frame, _SPINE_DELTA_IDS)

    return frame


def install_output_quality_hardening(reasoner_module: ModuleType) -> None:
    if getattr(reasoner_module, _MARKER, False):
        return
    original = getattr(reasoner_module, "build_contextual_reasoning_frame", None)
    if original is None:
        return

    def build_contextual_reasoning_frame(episode: Any, *, urgency: str = "ROUTINE") -> Any:
        frame = original(episode, urgency=urgency)
        return _clean_frame(frame, episode)

    reasoner_module.build_contextual_reasoning_frame = build_contextual_reasoning_frame
    setattr(reasoner_module, _MARKER, True)
