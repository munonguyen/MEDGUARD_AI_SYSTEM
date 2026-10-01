"""V27.3 metadata hardening for conversation routing and symptom guidance.

These adapters correct bounded classification metadata without changing clinical
urgency. They prevent respiratory speech limitation from becoming a neurologic
episode and prevent the word ``cổ`` inside ``cổ họng`` from selecting a
neck/shoulder self-care guide.
"""

from __future__ import annotations

import re
from types import ModuleType
from typing import Any

from app.services.clinical_text import normalize_search_text


_RISK_MARKER = "_medguard_v27_3_risk_memory_metadata"
_TRIAGE_MARKER = "_medguard_v27_3_triage_guidance_metadata"


def _respiratory_speech_limitation(text: str) -> bool:
    norm = normalize_search_text(str(text or ""))
    speech = bool(
        re.search(
            r"\b(?:kho noi cau dai|khong noi tron cau|khong noi duoc cau dai|noi cau dai)\b",
            norm,
        )
    )
    respiratory = bool(
        re.search(r"\b(?:hut hoi|kho tho|tho gap|tho doc|nghet tho|kho lay hoi)\b", norm)
    )
    focal_neuro = bool(
        re.search(
            r"\b(?:noi ngong|noi diu|meo mieng|lech mieng|yeu tay|yeu chan|"
            r"yeu nua nguoi|te nua nguoi|khong tim duoc tu|mat ngon ngu)\b",
            norm,
        )
    )
    return speech and respiratory and not focal_neuro


def install_risk_memory_metadata_hardening(module: ModuleType) -> None:
    if getattr(module, _RISK_MARKER, False):
        return
    original = getattr(module, "infer_episode_domain", None)
    if original is None:
        return

    def infer_episode_domain(text: str):
        # A patient who cannot sustain a long sentence *because of dyspnea* has
        # respiratory functional limitation, not aphasia. Keep genuine focal
        # speech deficits on the original neurologic path.
        if _respiratory_speech_limitation(text):
            return "cardiorespiratory"
        return original(text)

    module.infer_episode_domain = infer_episode_domain
    setattr(module, _RISK_MARKER, True)


def _throat_only_neck_false_match(text: str) -> bool:
    norm = normalize_search_text(str(text or ""))
    throat = bool(
        re.search(
            r"\b(?:co hong|nghen hong|hong dau|dau hong|rat hong|kho nuot|nuot dau|hong kho chiu)\b",
            norm,
        )
    )
    true_neck_or_shoulder = bool(
        re.search(
            r"\b(?:dau co|moi co|cung co|cang co|xoay co.*dau|dau gay|co gay|"
            r"vai gay|dau vai|moi vai|cang vai)\b",
            norm,
        )
    )
    return throat and not true_neck_or_shoulder


class _TriageKnowledgeProxy:
    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped

    def find_symptom_guidance(self, text: str):
        guidance = self._wrapped.find_symptom_guidance(text)
        if (
            isinstance(guidance, dict)
            and str(guidance.get("topic") or "") == "neck_shoulder_pain"
            and _throat_only_neck_false_match(text)
        ):
            return None
        return guidance

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)


def install_triage_guidance_metadata_hardening(module: ModuleType) -> None:
    if getattr(module, _TRIAGE_MARKER, False):
        return
    current = getattr(module, "knowledge", None)
    if current is None:
        return
    module.knowledge = _TriageKnowledgeProxy(current)
    setattr(module, _TRIAGE_MARKER, True)
