"""Patient-facing response enrichment after domain authority has resolved.

This module is presentation-only.  It may improve summary wording and actionable
next steps from an already-resolved result, but it must never change intent,
clinical facts, severity, emergency locks, medication decisions, or persisted
workflow state.
"""

from __future__ import annotations

from typing import Any


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))


def _monitoring_updates(
    *, status: str, result: dict[str, Any] | None, summary: str, next_steps: list[str]
) -> tuple[str, list[str]]:
    if status == "needs_information" or not isinstance(result, dict):
        if not next_steps:
            next_steps.extend(
                [
                    "Kiểm tra lại tên chỉ số, giá trị và đơn vị trên thiết bị rồi gửi đầy đủ để hệ thống đọc đúng phép đo.",
                    "Nếu đang thấy khó thở, đau ngực, ngất, lú lẫn hoặc triệu chứng nặng nhanh, hãy đi khám/cấp cứu thay vì chờ thêm số đo.",
                ]
            )
        return summary, _dedupe(next_steps)

    escalation = str(result.get("escalation_level") or "NONE").upper()
    trend = str(result.get("trend") or "insufficient_data").lower()

    if escalation == "EMERGENCY":
        summary = (
            "Mình hiểu một chỉ số bất thường có thể khiến bạn lo. Số đo hiện tại đã chạm ngưỡng cấu hình cần đánh giá cấp cứu; "
            "chỉ số này không đủ để xác định nguyên nhân, vì vậy ưu tiên là được đánh giá trực tiếp ngay."
        )
        next_steps = [
            "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay; nếu đang choáng, khó thở, đau ngực hoặc yếu lả thì không tự lái xe.",
            "Mang theo hoặc chụp lại kết quả đo và danh sách thuốc đang dùng để nhân viên y tế kiểm tra nhanh hơn.",
            *next_steps,
        ]
    elif escalation == "URGENT":
        summary = (
            "Mình hiểu bạn muốn biết số đo này có đáng lo. Kết quả đã nằm trong vùng cần được nhân viên y tế đánh giá sớm; "
            "một chỉ số đơn lẻ chưa đủ để xác định nguyên nhân."
        )
        next_steps = [
            "Liên hệ cơ sở y tế hoặc bác sĩ để được đánh giá sớm, đặc biệt nếu chỉ số tiếp tục xấu đi hoặc xuất hiện triệu chứng mới.",
            "Đo lại đúng kỹ thuật và ghi lại thời điểm, giá trị, đơn vị để theo dõi diễn biến trong lúc chờ đánh giá.",
            *next_steps,
        ]
    elif escalation == "CLINIC":
        summary = (
            "Số đo hiện tại chưa ở mức cấp cứu theo ngưỡng cấu hình nhưng nên được đối chiếu với triệu chứng và các lần đo khác. "
            "Hệ thống không thể xác định nguyên nhân chỉ từ một phép đo."
        )
        next_steps = [
            "Sắp xếp đi khám hoặc liên hệ bác sĩ nếu chỉ số còn bất thường, tái diễn hoặc đi kèm triệu chứng khó chịu.",
            "Đo lại đúng kỹ thuật và theo dõi các giá trị tiếp theo để có xu hướng rõ hơn.",
            *next_steps,
        ]
    else:
        trend_text = (
            "Hiện chưa đủ số lần đo để kết luận xu hướng."
            if trend == "insufficient_data"
            else "Xu hướng hiện tại đã được hệ thống ghi nhận nhưng vẫn cần đối chiếu với triệu chứng và kỹ thuật đo."
        )
        summary = (
            "Mình hiểu bạn muốn biết trị số này có đáng lo. Số đo hiện tại chưa chạm ngưỡng cảnh báo trong bộ quy tắc đang dùng. "
            f"{trend_text} Một phép đo đơn lẻ không đủ để khẳng định tình trạng sức khỏe."
        )
        next_steps = [
            "Đo lại đúng kỹ thuật ở thời điểm phù hợp và ghi lại giá trị cùng đơn vị để kiểm tra tính nhất quán.",
            "Theo dõi triệu chứng; nếu xuất hiện đau ngực, khó thở, ngất, lú lẫn hoặc tình trạng xấu nhanh, hãy đi khám/cấp cứu ngay.",
            *next_steps,
        ]

    return summary, _dedupe(next_steps)


def enrich_patient_surface(
    *,
    intent: str,
    status: str,
    reply: str,
    result: dict[str, Any] | None,
    answer: Any,
) -> Any:
    """Return an enriched answer without altering the authoritative result."""
    if answer is None:
        return answer

    summary = str(getattr(answer, "summary", "") or "")
    next_steps = list(getattr(answer, "next_steps", []) or [])

    if intent == "monitoring":
        summary, next_steps = _monitoring_updates(
            status=status,
            result=result,
            summary=summary,
            next_steps=next_steps,
        )

    elif intent == "schedule" and status == "answered":
        next_steps.extend(
            [
                "Kiểm tra card lịch thuốc để xác nhận đúng tên thuốc, giờ nhắc và trạng thái hiện tại.",
                "Theo dõi card sau mỗi lần chỉnh sửa; nếu lịch không còn phù hợp, hãy cập nhật hoặc tạm dừng card thay vì tạo trùng lịch.",
            ]
        )

    elif intent == "followup":
        if not next_steps:
            next_steps.extend(
                [
                    "Liên hệ cơ sở y tế hoặc lịch khám của bạn để chọn thời điểm tái khám phù hợp với diễn biến hiện tại.",
                    "Nếu muốn hệ thống tạo mốc cụ thể, hãy cho biết thời điểm hoặc khoảng thời gian bạn có thể đi khám.",
                ]
            )

    elif intent == "safety":
        if status == "needs_information":
            next_steps.extend(
                [
                    "Kiểm tra tên thuốc, hoạt chất và hàm lượng trên nhãn hoặc đơn thuốc rồi gửi lại chính xác để đối chiếu.",
                    "Trong lúc chưa xác định được thuốc, không tự thêm, đổi liều hoặc phối hợp thuốc; hãy trao đổi với bác sĩ hoặc dược sĩ nếu cần dùng ngay.",
                ]
            )
        elif not next_steps:
            next_steps.extend(
                [
                    "Không tự thêm hoặc đổi liều thuốc chỉ dựa trên hội thoại; kiểm tra lại nhãn thuốc và các thuốc đang dùng.",
                    "Trao đổi với bác sĩ hoặc dược sĩ nếu cần phối hợp thuốc, đổi liều hoặc nếu xuất hiện phản ứng bất thường.",
                ]
            )

    elif intent in {"pharmacy", "ocr", "authenticity"} and not next_steps:
        next_steps.append(
            "Kiểm tra lại thông tin đầu vào và liên hệ dược sĩ hoặc nhân viên y tế nếu kết quả này ảnh hưởng đến việc dùng thuốc."
        )

    next_steps = _dedupe(next_steps)
    if summary == getattr(answer, "summary", "") and next_steps == list(getattr(answer, "next_steps", []) or []):
        return answer
    return answer.model_copy(update={"summary": summary, "next_steps": next_steps})
