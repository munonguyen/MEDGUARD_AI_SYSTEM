"""V27.2 medication conversation policy.

This module does not evaluate drug interactions and does not author treatment.
It closes two conversation-quality gaps around the existing Safety Kernel:

* broader recognition of requests for personalised dose changes; and
* context-aware missing-information prompts that acknowledge the latest turn
  instead of repeating one generic sentence across unrelated medication cases.

All actual medication-risk decisions remain owned by the existing safety
service and its versioned knowledge tables.
"""

from __future__ import annotations

import re
from types import ModuleType
from typing import Any

from app.services.clinical_text import normalize_search_text


_MARKER = "_medguard_v27_2_medication_conversation_policy"
_GENERIC_MISSING_MEDICATION_REPLY = (
    "Tôi cần tên thuốc đang cân nhắc hoặc thuốc muốn phối hợp để kiểm tra."
)


def _latest_user_text(payload: Any) -> str:
    for message in reversed(getattr(payload, "messages", ()) or ()):
        if getattr(message, "role", None) == "user":
            value = str(getattr(message, "content", "") or "").strip()
            if value:
                return value
    return ""


def _prior_user_text(payload: Any) -> str:
    values: list[str] = []
    for message in (getattr(payload, "messages", ()) or ())[:-1]:
        if getattr(message, "role", None) != "user":
            continue
        value = str(getattr(message, "content", "") or "").strip()
        if value:
            values.append(value)
    return " ".join(values[-3:])


def _bounded_turn(text: str, *, limit: int = 180) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip().rstrip("?.! ")
    if len(value) > limit:
        value = value[: limit - 3].rstrip() + "..."
    return value


def _is_personalized_dose_request(normalized: str) -> bool:
    """Recognize common Vietnamese dose-changing language conservatively."""
    return bool(
        "tu doi lieu" in normalized
        or "tu bo lieu" in normalized
        or "bo lieu thuoc" in normalized
        or "nua lieu" in normalized
        or "dung xen ke" in normalized
        or "uong xen ke" in normalized
        or re.search(r"\blieu\s+[a-z0-9._+-]+\s+cu the\b", normalized)
        or re.search(r"\blieu\s+cu the\b", normalized)
        or re.search(r"\b(?:tang|giam|doi|bo)\s+lieu\b", normalized)
    )


def _contextual_missing_reply(payload: Any) -> str:
    latest = _latest_user_text(payload)
    normalized = normalize_search_text(latest)
    history = normalize_search_text(_prior_user_text(payload))
    latest_bounded = _bounded_turn(latest)
    grounding = f"Dữ kiện mới ở lượt này: {latest_bounded}. " if latest_bounded else ""

    ingestion_context = any(
        marker in normalized or marker in history
        for marker in (
            "da uong",
            "lo uong",
            "uong nham",
            "gap doi",
            "qua lieu",
        )
    )
    if "gay non" in normalized:
        return (
            f"{grounding}Đây là câu hỏi xử trí sau khi thuốc đã được dùng, không phải một thuốc đang cân nhắc. "
            "Để đánh giá nguy cơ chính xác, cần tên/hoạt chất, hàm lượng, số lượng đã uống và thời điểm uống."
        )
    if ingestion_context:
        return (
            f"{grounding}Ngữ cảnh cho thấy thuốc đã được dùng. Để đánh giá tiếp, cần tên hoặc hoạt chất, "
            "hàm lượng, số lượng đã dùng và thời điểm dùng; không nên coi đây là một câu hỏi phối hợp thuốc mới."
        )

    if "thuc pham bo sung" in history or "thao duoc" in normalized or "khong co ham luong" in normalized:
        return (
            f"{grounding}Không thể xác nhận phối hợp an toàn khi thành phần hoặc hàm lượng của sản phẩm chưa rõ. "
            "Cần tên sản phẩm, danh sách thành phần/hoạt chất và hàm lượng trên nhãn để kiểm tra tiếp."
        )

    if "chong dong" in normalized or "chong dong" in history:
        return (
            f"{grounding}Cần tên cụ thể của thuốc chống đông và liều đang dùng để kiểm tra đúng thuốc; "
            "không nên tự thay đổi hoặc bỏ liều chỉ dựa trên hội thoại."
        )

    if "ruou" in normalized or "ruou" in history or "thuoc ngu" in normalized or "gay buon ngu" in normalized:
        return (
            f"{grounding}Chưa thể xác nhận an toàn khi chưa biết chính xác thuốc gây buồn ngủ/thuốc ngủ nào đang được cân nhắc. "
            "Cần tên hoặc hoạt chất và hàm lượng trên nhãn để kiểm tra tương tác trong bối cảnh đã uống rượu."
        )

    if "viem loet da day" in normalized or "da day" in normalized:
        return (
            f"{grounding}Tiền sử dạ dày là dữ kiện cần giữ cùng thuốc ở các lượt trước. "
            "Cần xác nhận chính xác tên/hoạt chất và hàm lượng của thuốc đang dùng hoặc định dùng để đánh giá an toàn."
        )

    if any(marker in normalized for marker in ("dau hieu nao", "kham gap", "cap cuu", "khi nao can")):
        return (
            f"{grounding}Để gắn dấu hiệu cảnh báo với đúng thuốc và tình huống đã nêu, cần giữ tên/hoạt chất của thuốc ở lượt trước. "
            "Nếu tên thuốc chưa rõ, hãy cung cấp ảnh nhãn hoặc tên hoạt chất thay vì tự dùng thêm."
        )

    if "metformin" in normalized:
        return (
            f"{grounding}Metformin đã được xác định, nhưng việc đổi liều cá nhân hóa không nên quyết định chỉ từ một tin nhắn hoặc một lần đo. "
            "Cần kế hoạch dùng thuốc hiện tại và các chỉ số liên quan để bác sĩ hoặc dược sĩ rà soát."
        )

    return (
        f"{grounding}Chưa đủ dữ kiện để kiểm tra an toàn thuốc. "
        "Hãy cung cấp tên hoặc hoạt chất, hàm lượng và cho biết thuốc đã dùng hay mới đang cân nhắc."
    )


def install_medication_conversation_policy(chat_module: ModuleType) -> None:
    if getattr(chat_module, _MARKER, False):
        return

    original_dose = getattr(chat_module, "_requests_personalized_dose", None)
    original_response = getattr(chat_module, "_response", None)
    if original_dose is None or original_response is None:
        return

    def _requests_personalized_dose(normalized_text: str) -> bool:
        normalized = normalize_search_text(normalized_text)
        return bool(original_dose(normalized_text) or _is_personalized_dose_request(normalized))

    def _response(payload: Any, ctx: Any, **kwargs: Any):
        intent = str(kwargs.get("intent") or "")
        status = str(kwargs.get("status") or "")
        reply = str(kwargs.get("reply") or "")
        if (
            intent == "safety"
            and status == "needs_information"
            and reply.strip() == _GENERIC_MISSING_MEDICATION_REPLY
        ):
            kwargs["reply"] = _contextual_missing_reply(payload)
        return original_response(payload, ctx, **kwargs)

    chat_module._requests_personalized_dose = _requests_personalized_dose
    chat_module._response = _response
    setattr(chat_module, _MARKER, True)
