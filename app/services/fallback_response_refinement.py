"""Bounded V27.5 refinement for deterministic clinical fallback summaries.

This module does not reason clinically. It only promotes already-approved facts
or actions from the deterministic answer so the compact fallback ``summary``
responds to the current concern instead of repeating a generic explanation.
Safety Kernel decisions and all structured fields remain unchanged.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.models.chat import GroundedAnswer
from app.services.clinical_agent_contract import ClinicalAgentContract


_FACT_PREFIXES = (
    "Dấu hiệu đã được xác nhận từ bệnh cảnh hiện tại:",
    "Dấu hiệu được nhận diện:",
)
_SKIP_KEY_POINT_PREFIXES = (
    "Hướng chuyên khoa hiện tại:",
    "Chuyên khoa:",
)


def _norm(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", str(value or "").strip().lower())
    normalized = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    ).replace("đ", "d")
    normalized = re.sub(r"[^a-z0-9%]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _sentence(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if text and text[-1] not in ".?!":
        text += "."
    return text


def _bounded_patient_fact(answer: GroundedAnswer) -> str:
    """Select one already-approved patient fact without adding interpretation."""
    for raw in answer.key_points:
        text = re.sub(r"\s+", " ", str(raw or "").strip())
        if not text or any(text.startswith(prefix) for prefix in _SKIP_KEY_POINT_PREFIXES):
            continue
        for prefix in _FACT_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break
        if not text:
            continue
        text = re.sub(r"^(?:Tôi|Mình)\s+", "Bạn ", text, flags=re.I)
        if len(text) > 180:
            text = text[:177].rstrip() + "..."
        return _sentence(text)
    return ""


def _latest_user_text(contract: ClinicalAgentContract) -> str:
    envelope = contract.envelope
    result = envelope.get("clinical_result")
    latest = ""
    if isinstance(result, dict):
        latest = str(result.get("conversation_turn") or "").strip()
    if not latest:
        latest = str(envelope.get("user_question") or "").strip()
    marker = "lượt hiện tại:"
    lowered = latest.lower()
    if marker in lowered:
        latest = latest[lowered.rfind(marker) + len(marker):].strip()
    lines = [line.strip() for line in latest.splitlines() if line.strip()]
    return lines[-1] if lines else latest


def _approved_current_action(answer: GroundedAnswer) -> str:
    """Select an existing conservative action; never synthesize medication advice."""
    preferred_markers = (
        "không tự bắt đầu",
        "không tự dùng",
        "không dùng thêm",
        "trao đổi với bác sĩ hoặc dược sĩ",
    )
    for marker in preferred_markers:
        for step in answer.next_steps:
            text = str(step or "").strip()
            if marker in text.lower():
                return _sentence(text)
    return ""


def refine_contract_fallback(
    answer: GroundedAnswer,
    contract: ClinicalAgentContract,
) -> GroundedAnswer:
    """Promote one relevant approved fact/action into the fallback summary.

    * Emergency output is untouched.
    * Triage may lead with one fact already present in ``key_points`` when the
      summary otherwise omits it.
    * Medication-safety questions explicitly asking what to do now may lead with
      an action already present in ``next_steps``.
    * No structured clinical field is mutated.
    """
    envelope = contract.envelope
    safety = envelope.get("safety_constraints")
    result = envelope.get("clinical_result")
    urgency = "ROUTINE"
    if isinstance(safety, dict):
        urgency = str(safety.get("urgency_floor") or urgency).upper()
    if isinstance(result, dict):
        urgency = str(result.get("urgency") or result.get("escalation_level") or urgency).upper()
    if urgency == "EMERGENCY":
        return answer

    intent = str(envelope.get("intent") or "")
    summary = str(answer.summary or "").strip()
    promoted = ""

    if intent == "triage":
        fact = _bounded_patient_fact(answer)
        if fact and _norm(fact).rstrip(" ") not in _norm(summary):
            # A shorter containment check catches the same fact with only
            # punctuation/prefix differences while still allowing a distinct
            # current-turn fact to improve specificity.
            fact_core = _norm(fact).rstrip(" .?!")
            if fact_core and fact_core not in _norm(summary):
                promoted = fact

    elif intent == "safety":
        latest = _norm(_latest_user_text(contract))
        action_request = any(
            marker in latest
            for marker in (
                "buoc an toan nhat",
                "nen lam gi",
                "toi nen lam gi",
                "chua uong",
                "chua dung",
            )
        )
        if action_request:
            action = _approved_current_action(answer)
            if action and _norm(action).rstrip(" .?!") not in _norm(summary):
                promoted = action

    if not promoted:
        return answer

    return answer.model_copy(
        update={"summary": f"{promoted} {summary}".strip()}
    )
