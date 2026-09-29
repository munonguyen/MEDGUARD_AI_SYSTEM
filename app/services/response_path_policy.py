"""V27 response-path invariant helpers.

This small policy module makes the architectural decision independently testable:
clinicality determines whether the agent-first clinical contract is used;
``answered`` versus ``needs_information`` is only an outcome state.
"""

from __future__ import annotations

from typing import Any

from app.models.chat import ChatIntent


CLINICAL_TASKS = frozenset({
    "LAB_INTERPRETATION",
    "EXPOSURE_REACTION",
    "PERIPHERAL_JOINT",
})


def is_clinical_response_path(
    *,
    intent: ChatIntent,
    clinical_task_name: str | None,
) -> bool:
    return intent in {"triage", "safety"} or clinical_task_name in CLINICAL_TASKS


def clinical_payload_with_outcome(
    result: Any,
    *,
    status: str,
    required_fields: list[str],
    extracted: dict[str, Any],
) -> dict[str, Any]:
    payload = dict(result) if isinstance(result, dict) else {}
    payload["_response_status"] = status
    payload["required_fields"] = list(required_fields)
    payload["extracted"] = dict(extracted)
    return payload
