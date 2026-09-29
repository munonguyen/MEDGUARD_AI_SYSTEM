"""Canonical patient-visible response surface for V27.

The frontend and offline evaluation must score the same text.  This module is
intentionally presentation-only: it does not change clinical severity, infer
facts, or author medical content.  It mirrors the V27 frontend authority rule:

verified + non-legacy narrative -> canonical narrative
otherwise                      -> deterministic fallback surface

Safety Kernel urgency remains metadata/overlay and is never concatenated into
the prose sent to Jev as if it were Writer-authored text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


_LEGACY_QUESTION_PREFIXES = (
    "Bạn cho mình biết thêm:",
    "Thông tin cần báo nhân viên y tế nếu có thể:",
)


@dataclass(frozen=True)
class PatientVisibleSurface:
    text: str
    source: str
    verification_status: str
    safety_urgency: str | None = None

    @property
    def is_verified_canonical(self) -> bool:
        return self.source == "canonical_verified_narrative"


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    return {}


def _clean_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _visible_narrative(answer: Mapping[str, Any]) -> list[str]:
    raw = answer.get("narrative") or []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []

    blocks: list[str] = []
    for item in raw:
        if isinstance(item, Mapping):
            text = _clean_text(item.get("text"))
        else:
            text = _clean_text(getattr(item, "text", item))
        if not text:
            continue
        if any(text.startswith(prefix) for prefix in _LEGACY_QUESTION_PREFIXES):
            continue
        blocks.append(text)
    return blocks


def _deterministic_fallback_text(answer: Mapping[str, Any]) -> str:
    """Approximate the prose-bearing fallback surface rendered by the UI.

    This is intentionally *not* used for verified responses.  It exists only so
    offline regression can prove that a verified response never silently falls
    back to hidden deterministic title/summary/key-points.
    """
    parts: list[str] = []

    for scalar_key in ("title", "summary"):
        value = _clean_text(answer.get(scalar_key))
        if value:
            parts.append(value)

    for list_key, limit in (
        ("key_points", 5),
        ("clinical_hypotheses", 4),
        ("next_steps", 5),
        ("safety_notes", 4),
        ("display_questions", 2),
        ("limitations", 2),
    ):
        values = answer.get(list_key)
        if list_key == "display_questions" and not isinstance(values, list):
            values = answer.get("questions")
        if not isinstance(values, list):
            continue
        for value in values[:limit]:
            text = _clean_text(value)
            if text:
                parts.append(text)

    return "\n".join(dict.fromkeys(parts)).strip()


def select_patient_visible_surface(response: Any) -> PatientVisibleSurface:
    """Return exactly the prose surface that V27 considers patient-visible.

    ``response`` may be a ChatResponse model or a JSON-compatible mapping.
    The selection rule deliberately keys off ``verification_status`` plus a
    non-empty filtered narrative, matching ``GroundedAnswer.jsx``.
    """
    payload = _as_dict(response)
    answer = _as_dict(payload.get("answer"))
    result = _as_dict(payload.get("result"))

    verification_status = _clean_text(payload.get("verification_status") or "not_requested")
    narrative = _visible_narrative(answer)
    urgency = _clean_text(result.get("urgency") or result.get("escalation_level")) or None

    if verification_status == "verified" and narrative:
        return PatientVisibleSurface(
            text="\n".join(narrative),
            source="canonical_verified_narrative",
            verification_status=verification_status,
            safety_urgency=urgency,
        )

    return PatientVisibleSurface(
        text=_deterministic_fallback_text(answer),
        source="deterministic_fallback",
        verification_status=verification_status,
        safety_urgency=urgency,
    )


def assert_benchmark_surface_is_patient_visible(
    response: Any,
    benchmark_text: str,
) -> PatientVisibleSurface:
    """Fail closed when an evaluator scores anything other than visible prose."""
    surface = select_patient_visible_surface(response)
    candidate = _clean_text(benchmark_text)
    if not candidate:
        raise ValueError("benchmark candidate is empty")
    if candidate != surface.text:
        raise ValueError(
            "benchmark_surface_mismatch: evaluator text must equal canonical patient-visible surface"
        )
    return surface
