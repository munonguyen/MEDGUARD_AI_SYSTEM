"""V27.2/V27.3 patient-language composers for deterministic domain answers.

The domain services continue to own risk and actions. This module only converts
machine-oriented labels into concise patient language and removes presentation
artifacts. It must never truncate the complete clinical question candidate set
or replace a domain-specific emergency/hard-stop action.
"""

from __future__ import annotations

import re
from types import ModuleType
from typing import Any


_MARKER = "_medguard_v27_2_answering_patch"
_INTERNAL_KEY_PREFIXES = (
    "Mức phân luồng:",
    "Mã ưu tiên nội bộ:",
    "Hướng tiếp nhận do quy tắc lựa chọn:",
)
_INTERNAL_LIMITATION_MARKERS = (
    "nguồn tri thức đang chờ",
    "cơ chế được mô tả là giả thuyết làm việc",
)
_KEY_POINT_PREFIXES = (
    "Dấu hiệu đã được xác nhận từ bệnh cảnh hiện tại:",
    "Dấu hiệu được nhận diện:",
)


def _clean_machine_language(text: str) -> str:
    value = str(text or "")
    replacements = {
        "insufficient_data": "chưa đủ dữ liệu để đánh giá xu hướng",
        "HIGH": "cao",
        "MODERATE": "trung bình",
        "LOW": "thấp",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = re.sub(r"\bMức chuyển tuyến hiện tại:\s*NONE\b[;,.]?", "", value, flags=re.I)
    value = re.sub(r"\bESI\s*[1-5]\b", "", value, flags=re.I)
    # Structured red-flag strings sometimes already include a terminal period;
    # composers must not append a second one. Collapse presentation punctuation
    # only; this does not alter any clinical claim or action.
    value = re.sub(r"\.{2,}", ".", value)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    return re.sub(r"\s{2,}", " ", value).strip(" ;")


def _format_medication_list(values: Any) -> str:
    if not isinstance(values, list):
        return ""
    names = [str(v).replace("_", " ").strip() for v in values if str(v).strip()]
    names = list(dict.fromkeys(names))
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " và " + names[-1]


def _measurement_summary(result: dict[str, Any]) -> str:
    values = result.get("patient_measurements")
    if not isinstance(values, list):
        return ""
    by_metric: dict[str, tuple[Any, str]] = {}
    for item in values:
        if not isinstance(item, dict):
            continue
        by_metric[str(item.get("metric"))] = (item.get("value"), str(item.get("unit") or ""))

    if "systolic" in by_metric and "diastolic" in by_metric:
        systolic = by_metric["systolic"][0]
        diastolic = by_metric["diastolic"][0]
        return f"Huyết áp bạn vừa gửi là {systolic:g}/{diastolic:g} mmHg"

    labels = {
        "spo2": "SpO₂",
        "heart_rate": "Nhịp tim",
        "temperature_c": "Nhiệt độ",
        "glucose_mg_dl": "Đường huyết",
        "pain_score": "Mức đau",
    }
    parts: list[str] = []
    for metric, (value, unit) in by_metric.items():
        if metric in {"systolic", "diastolic"}:
            continue
        label = labels.get(metric, metric.replace("_", " "))
        display = f"{value:g}" if isinstance(value, (int, float)) else str(value)
        parts.append(f"{label} {display}{(' ' + unit) if unit else ''}")
    return ", ".join(parts)


def _plain_escalation(level: str) -> tuple[str, str]:
    value = str(level or "NONE").upper()
    mapping = {
        "EMERGENCY": (
            "Chỉ số cần được đánh giá cấp cứu",
            "Giá trị này nằm trong vùng cảnh báo cần được đánh giá cấp cứu ngay.",
        ),
        "URGENT": (
            "Chỉ số cần được đánh giá sớm",
            "Giá trị này cần được nhân viên y tế đánh giá sớm.",
        ),
        "CLINIC": (
            "Bạn nên liên hệ cơ sở y tế",
            "Giá trị này nên được trao đổi với cơ sở y tế để được đánh giá phù hợp.",
        ),
        "SELF_CARE": (
            "Tiếp tục theo dõi",
            "Chưa có dấu hiệu cần chuyển tuyến ngay từ chỉ số này; tiếp tục theo dõi theo hướng dẫn.",
        ),
        "NONE": (
            "Chưa có ngưỡng cảnh báo từ lần đo này",
            "Lần đo hiện tại chưa chạm ngưỡng cảnh báo đã cấu hình.",
        ),
    }
    return mapping.get(value, ("Kết quả theo dõi", "Đã đối chiếu giá trị với ngưỡng theo dõi hiện có."))


def _plain_trend(value: Any) -> str:
    trend = str(value or "unknown")
    return {
        "insufficient_data": "Chưa đủ số lần đo để đánh giá xu hướng.",
        "unknown": "Chưa đủ số lần đo để đánh giá xu hướng.",
        "stable": "Các lần đo hiện có chưa cho thấy thay đổi đáng kể.",
        "improving": "Xu hướng các lần đo đang cải thiện.",
        "worsening": "Xu hướng hoặc ngưỡng hiện tại cần được chú ý hơn.",
    }.get(trend, "")


def _clean_list(values: Any, *, limit: int | None = None) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    cleaned = [
        _clean_machine_language(str(value))
        for value in values
        if str(value).strip()
    ]
    unique = list(dict.fromkeys(value for value in cleaned if value))
    return unique if limit is None else unique[:limit]


def _looks_like_transcript_blob(value: str) -> bool:
    """Detect duplicated multi-turn transcript accidentally exposed as a key point."""
    raw_lines = [re.sub(r"\s+", " ", line).strip() for line in str(value).splitlines() if line.strip()]
    if len(raw_lines) < 3:
        return False
    normalized = [line.lower().rstrip("?.! ") for line in raw_lines]
    repeated = len(normalized) >= 4 and len(set(normalized)) * 2 <= len(normalized)
    oversized_history = len(value) > 420 and len(raw_lines) >= 3
    return repeated or oversized_history


def _key_point_identity(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    for prefix in _KEY_POINT_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip()
            break
    return normalized.lower().rstrip(" .;:!?-")


def _clean_key_points(values: Any, *, limit: int = 5) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        original = str(raw or "")
        if not original.strip() or original.startswith(_INTERNAL_KEY_PREFIXES):
            continue
        if _looks_like_transcript_blob(original):
            continue
        cleaned = _clean_machine_language(original)
        if not cleaned:
            continue
        identity = _key_point_identity(cleaned)
        if not identity or identity in seen:
            continue
        seen.add(identity)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _sanitize_answer(answer: Any) -> Any:
    limitations = [
        _clean_machine_language(str(value))
        for value in list(getattr(answer, "limitations", None) or ())
        if str(value).strip()
        and not any(marker in str(value).lower() for marker in _INTERNAL_LIMITATION_MARKERS)
    ]
    return answer.model_copy(
        update={
            "title": _clean_machine_language(getattr(answer, "title", "")),
            "summary": _clean_machine_language(getattr(answer, "summary", "")),
            "key_points": _clean_key_points(getattr(answer, "key_points", None), limit=5),
            "next_steps": _clean_list(getattr(answer, "next_steps", None), limit=6),
            "safety_notes": _clean_list(getattr(answer, "safety_notes", None), limit=5),
            # ``questions`` is the complete approved audit/reasoning pool. The
            # ChatResponse dialogue-policy validator alone controls the smaller
            # patient-visible ``display_questions`` set.
            "questions": _clean_list(getattr(answer, "questions", None)),
            "display_questions": _clean_list(getattr(answer, "display_questions", None), limit=2),
            "limitations": list(dict.fromkeys(value for value in limitations if value))[:2],
        }
    )


def install_v27_2_answering_patch(answering_module: ModuleType) -> None:
    if getattr(answering_module, _MARKER, False):
        return

    original_safety = getattr(answering_module, "_safety_answer", None)
    original_monitoring = getattr(answering_module, "_monitoring_answer", None)
    original_with_narrative = getattr(answering_module, "_with_narrative", None)
    if not all((original_safety, original_monitoring, original_with_narrative)):
        return

    def _safety_answer(result: dict[str, Any], sources: list[Any]):
        answer = original_safety(result, sources)
        # Preserve domain-specific hard-stop/emergency wording and action order.
        # This layer only adds remembered context when it is not already visible.
        current = _format_medication_list(result.get("conversation_current_medications"))
        proposed = _format_medication_list(result.get("conversation_proposed_medications"))
        lead = ""
        if current and proposed:
            lead = f"Bạn đang dùng {current} và đang cân nhắc {proposed}."
        elif proposed:
            lead = f"Thuốc bạn đang cân nhắc là {proposed}."
        elif current:
            lead = f"Các thuốc đang dùng được ghi nhận gồm {current}."

        summary = str(answer.summary or "").strip()
        if lead:
            med_tokens = [value for value in (current, proposed) if value]
            if not all(token.lower() in summary.lower() for token in med_tokens):
                summary = f"{lead} {summary}".strip()

        return _sanitize_answer(answer.model_copy(update={"summary": summary}))

    def _monitoring_answer(result: dict[str, Any], sources: list[Any]):
        answer = original_monitoring(result, sources)
        if result.get("measurement_guidance"):
            return _sanitize_answer(answer)

        measurement = _measurement_summary(result)
        title, escalation_text = _plain_escalation(str(result.get("escalation_level", "NONE")))
        trend_text = _plain_trend(result.get("trend"))
        summary = " ".join(
            value
            for value in (
                measurement + "." if measurement else "",
                escalation_text,
                trend_text,
            )
            if value
        ).strip()
        return _sanitize_answer(answer.model_copy(update={"title": title, "summary": summary}))

    def _with_narrative(answer: Any, intent: Any):
        return original_with_narrative(_sanitize_answer(answer), intent)

    answering_module._safety_answer = _safety_answer
    answering_module._monitoring_answer = _monitoring_answer
    answering_module._with_narrative = _with_narrative
    setattr(answering_module, _MARKER, True)
