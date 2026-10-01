"""Canonical patient-visible response text for history and conversation context.

The API ``reply`` field remains a compact compatibility surface.  V27 verified
responses, however, are displayed from Writer-authored ``answer.narrative``.
This module makes the same authority decision available to backend persistence
and multi-turn context so the system remembers what the patient actually saw.

It is presentation/continuity logic only.  It never changes urgency, clinical
claims, actions or answer provenance.
"""

from __future__ import annotations

from app.models.chat import GroundedAnswer


_LEGACY_QUESTION_PREFIXES = (
    "Bạn cho mình biết thêm:",
    "Thông tin cần báo nhân viên y tế nếu có thể:",
)


def _visible_narrative_text(answer: GroundedAnswer | None) -> str:
    if answer is None:
        return ""
    blocks: list[str] = []
    for block in answer.narrative:
        text = str(block.text or "").strip()
        if not text:
            continue
        if any(text.startswith(prefix) for prefix in _LEGACY_QUESTION_PREFIXES):
            continue
        blocks.append(text)
    return "\n\n".join(blocks).strip()


def canonical_patient_response_text(
    *,
    answer: GroundedAnswer | None,
    verification_status: str | None,
    fallback_text: str,
) -> str:
    """Return the text that should represent the assistant in future context.

    This mirrors the frontend V27 authority contract: a verified answer with a
    non-empty narrative uses that narrative as canonical patient prose.  Every
    other state keeps the deterministic/compatibility fallback text.
    """
    if str(verification_status or "") == "verified":
        narrative = _visible_narrative_text(answer)
        if narrative:
            return narrative
    return str(fallback_text or "").strip()
