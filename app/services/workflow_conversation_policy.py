"""V27.2 patient-facing policy for deterministic workflow responses.

The underlying schedule and follow-up services remain authoritative. This layer
only turns their structured results into context-aware patient-facing wording:

* schedule confirmations repeat the actual active clock times; and
* follow-up planning that has no approved rule asks for an explicit clinician
  or user-provided date instead of presenting an internal rule-engine message.

No clinical interval, dose or treatment recommendation is invented here.
"""

from __future__ import annotations

from datetime import datetime
import re
from types import ModuleType
from typing import Any


_MARKER = "_medguard_v27_2_workflow_conversation_policy"


def _latest_user_text(payload: Any) -> str:
    for message in reversed(getattr(payload, "messages", ()) or ()):
        if getattr(message, "role", None) == "user":
            value = str(getattr(message, "content", "") or "").strip()
            if value:
                return value
    return ""


def _as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump(mode="json")
            return dict(dumped) if isinstance(dumped, dict) else {}
        except Exception:
            return {}
    return dict(value) if isinstance(value, dict) else {}


def _clock_time(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return f"{parsed.hour:02d}:{parsed.minute:02d}"
    except ValueError:
        match = re.search(r"(?:T|\s)([0-2]\d:[0-5]\d)", raw)
        return match.group(1) if match else None


def _active_schedule_times(result: Any) -> list[str]:
    data = _as_dict(result)
    schedules = data.get("schedules")
    if not isinstance(schedules, list):
        return []
    times: list[str] = []
    for schedule in schedules:
        item = _as_dict(schedule)
        if str(item.get("status") or "active") != "active":
            continue
        value = _clock_time(item.get("scheduled_at"))
        if value and value not in times:
            times.append(value)
    return sorted(times)


def _schedule_reply(original_reply: str, result: Any) -> str:
    data = _as_dict(result)
    action = str(data.get("action") or "")
    if action not in {"create", "view", "update"}:
        return original_reply
    times = _active_schedule_times(data)
    if not times:
        return original_reply
    if all(value in original_reply for value in times):
        return original_reply
    label = "Mốc giờ đang hoạt động" if len(times) > 1 else "Mốc giờ đang hoạt động"
    return f"{original_reply.strip()} {label}: {', '.join(times)}."


def _bounded_latest_request(payload: Any, *, limit: int = 180) -> str:
    value = re.sub(r"\s+", " ", _latest_user_text(payload)).strip().rstrip("?.! ")
    if len(value) > limit:
        value = value[: limit - 3].rstrip() + "..."
    return value


def _followup_reply(payload: Any, original_reply: str, result: Any) -> str:
    data = _as_dict(result)
    if bool(data.get("plan_available")):
        return original_reply
    latest = _bounded_latest_request(payload)
    grounding = f"Yêu cầu hiện tại của bạn là: {latest}. " if latest else ""
    return (
        f"{grounding}Hệ thống chưa có quy tắc tái khám đã được duyệt để tự chọn một mốc thời gian cho tình huống này. "
        "Hãy cung cấp ngày/giờ bạn muốn tái khám hoặc mốc bác sĩ đã dặn; hệ thống sẽ dùng mốc đó thay vì tự suy đoán khoảng tái khám."
    )


def install_workflow_conversation_policy(chat_module: ModuleType) -> None:
    if getattr(chat_module, _MARKER, False):
        return
    original_response = getattr(chat_module, "_response", None)
    if original_response is None:
        return

    def _response(payload: Any, ctx: Any, **kwargs: Any):
        intent = str(kwargs.get("intent") or "")
        result = kwargs.get("result")
        reply = str(kwargs.get("reply") or "")
        if intent == "schedule":
            kwargs["reply"] = _schedule_reply(reply, result)
        elif intent == "followup":
            kwargs["reply"] = _followup_reply(payload, reply, result)
        return original_response(payload, ctx, **kwargs)

    chat_module._response = _response
    setattr(chat_module, _MARKER, True)
