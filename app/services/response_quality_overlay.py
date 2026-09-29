"""Post-compose response quality improvements that do not change clinical authority.

This module is deliberately presentation-only.  It may improve summaries,
actionability and workflow guidance after a domain service has already produced
its result, but it must never change triage severity, warning facts, persisted
workflow state, or the emergency zero-question contract.
"""

from __future__ import annotations

from typing import Any


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))


def _monitoring_update(answer: Any, result: dict[str, Any]) -> Any:
    if result.get("measurement_guidance"):
        return answer

    escalation = str(result.get("escalation_level") or "NONE").upper()
    trend = str(result.get("trend") or "chưa xác định")
    next_steps = list(getattr(answer, "next_steps", []) or [])
    safety_notes = list(getattr(answer, "safety_notes", []) or [])

    if escalation == "EMERGENCY":
        summary = (
            "Chỉ số hiện tại nằm trong vùng nguy cơ cao và cần được đánh giá cấp cứu ngay; "
            f"xu hướng hiện được ghi nhận là {trend}."
        )
        next_steps = [
            "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay; không tự lái xe.",
            "Ngừng gắng sức, ở tư thế an toàn và nhờ người bên cạnh hỗ trợ trong khi chờ cấp cứu.",
            *next_steps,
        ]
        safety_notes = [
            "Không trì hoãn đánh giá cấp cứu để tiếp tục tự theo dõi chỉ số tại nhà.",
            *safety_notes,
        ]
    elif escalation == "URGENT":
        summary = (
            "Chỉ số hiện tại đang ngoài vùng an toàn và cần được nhân viên y tế đánh giá sớm; "
            f"xu hướng hiện được ghi nhận là {trend}."
        )
        next_steps = [
            "Ngừng gắng sức và nghỉ tại chỗ; nếu có thể, đo lại đúng kỹ thuật sau khi ổn định.",
            "Liên hệ cơ sở y tế để được đánh giá sớm trong ngày và mang theo các lần đo gần đây.",
            *next_steps,
        ]
        safety_notes = [
            "Nếu xuất hiện đau ngực, khó thở tăng, ngất, lú lẫn hoặc chỉ số xấu đi rõ rệt, hãy chuyển sang cấp cứu ngay.",
            *safety_notes,
        ]
    elif escalation == "CLINIC":
        summary = (
            "Chỉ số chưa ở mức cấp cứu theo ngưỡng hiện tại nhưng nên được trao đổi với cơ sở y tế; "
            f"xu hướng hiện được ghi nhận là {trend}."
        )
        next_steps = [
            "Ghi lại thời điểm, giá trị và điều kiện đo để cung cấp khi liên hệ cơ sở y tế.",
            *next_steps,
        ]
    else:
        summary = (
            "Chưa ghi nhận ngưỡng cảnh báo từ giá trị hiện tại; "
            f"xu hướng hiện được ghi nhận là {trend}."
        )
        if not next_steps:
            next_steps = [
                "Tiếp tục ghi lại các lần đo cùng thời điểm và cùng điều kiện để theo dõi xu hướng.",
                "Nếu giá trị thay đổi rõ rệt hoặc xuất hiện triệu chứng mới, hãy gửi lại cả chỉ số và triệu chứng kèm theo.",
            ]

    return answer.model_copy(
        update={
            "summary": summary,
            "next_steps": _dedupe(next_steps),
            "safety_notes": _dedupe(safety_notes),
            "questions": [] if escalation == "EMERGENCY" else list(getattr(answer, "questions", []) or []),
            "display_questions": [] if escalation == "EMERGENCY" else getattr(answer, "display_questions", None),
        }
    )


def _schedule_update(answer: Any, result: dict[str, Any]) -> Any:
    action = str(result.get("action") or "").lower()
    schedules = list(result.get("schedules") or [])
    active_count = sum(1 for item in schedules if str(item.get("status") or "active") == "active")
    key_points = list(getattr(answer, "key_points", []) or [])
    next_steps = list(getattr(answer, "next_steps", []) or [])

    if action in {"create", "update"}:
        key_points.append(f"Số card/mốc đang hoạt động trong kết quả thao tác: {active_count or len(schedules)}")
        next_steps.append("Mở card Lịch uống thuốc để kiểm tra lại tên thuốc và giờ nhắc vừa lưu.")
        next_steps.append("Nếu giờ hoặc tên thuốc chưa đúng, hãy yêu cầu sửa chính card hiện tại thay vì tạo card mới.")
    elif action in {"delete", "cancel", "pause", "remove"}:
        next_steps.append("Kiểm tra lại danh sách card để xác nhận lịch vừa chọn không còn ở trạng thái hoạt động.")
        next_steps.append("Nếu cần tạo lại lịch, hãy cung cấp tên thuốc và giờ muốn nhắc.")
    elif action in {"view", "list", "get"}:
        next_steps.append("Kiểm tra tên thuốc, giờ nhắc và trạng thái trên card; nếu cần thay đổi, hãy nói rõ card nào và giờ mới.")
    else:
        next_steps.append("Kiểm tra lại card Lịch uống thuốc để xác nhận trạng thái sau thao tác.")

    return answer.model_copy(
        update={
            "key_points": _dedupe(key_points),
            "next_steps": _dedupe(next_steps),
        }
    )


def _followup_update(answer: Any, result: dict[str, Any]) -> Any:
    next_steps = list(getattr(answer, "next_steps", []) or [])
    questions = list(getattr(answer, "questions", []) or [])

    if not bool(result.get("plan_available")):
        next_steps.extend([
            "Nếu bác sĩ hoặc cơ sở điều trị đã dặn một mốc tái khám, hãy cung cấp mốc đó để hệ thống ghi nhận chính xác.",
            "Nếu chưa có mốc hẹn, hãy liên hệ cơ sở điều trị để xác nhận thời điểm tái khám phù hợp thay vì tự chọn một khoảng thời gian cố định.",
        ])
        questions.append("Bạn có mốc tái khám hoặc hướng dẫn hẹn khám nào từ bác sĩ/cơ sở điều trị trước đó không?")
    else:
        suggestions = [str(value) for value in result.get("suggestions", []) if value]
        next_steps.extend(suggestions)
        if not next_steps:
            next_steps.append("Kiểm tra lại kế hoạch tái khám và xác nhận thời gian với cơ sở điều trị trước khi đi khám.")

    return answer.model_copy(
        update={
            "next_steps": _dedupe(next_steps),
            "questions": _dedupe(questions),
        }
    )


def _dose_refusal_update(answer: Any) -> Any:
    summary = str(getattr(answer, "summary", "") or "")
    normalized = summary.lower()
    if not any(marker in normalized for marker in ("không kê", "không kê hoặc tính liều", "không tính liều")):
        return answer

    next_steps = list(getattr(answer, "next_steps", []) or [])
    questions = list(getattr(answer, "questions", []) or [])
    next_steps.extend([
        "Không tự tăng, giảm, chia viên hoặc dùng xen kẽ liều dựa trên hội thoại này.",
        "Hãy mang tên thuốc, hàm lượng trên nhãn, bệnh nền và danh sách thuốc đang dùng để bác sĩ hoặc dược sĩ xác nhận liều phù hợp.",
    ])
    questions.append("Bạn có thể cho biết tên thuốc, hàm lượng ghi trên nhãn và mục đích đang định dùng thuốc không?")
    return answer.model_copy(
        update={
            "next_steps": _dedupe(next_steps),
            "questions": _dedupe(questions),
        }
    )


def enhance_response_answer(
    answer: Any,
    *,
    intent: str,
    status: str,
    result: dict[str, Any] | None,
) -> Any:
    """Improve patient-facing structure without changing the domain decision."""
    if answer is None:
        return answer

    if intent == "monitoring" and isinstance(result, dict):
        return _monitoring_update(answer, result)
    if intent == "schedule" and isinstance(result, dict) and status == "answered":
        return _schedule_update(answer, result)
    if intent == "followup" and isinstance(result, dict) and status == "answered":
        return _followup_update(answer, result)
    if intent == "safety" and status == "unsupported":
        return _dose_refusal_update(answer)
    return answer
