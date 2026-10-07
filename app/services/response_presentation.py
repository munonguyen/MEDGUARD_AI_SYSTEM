"""Choose disclosure depth, without deleting clinical source content."""
import re
from app.models.chat import GroundedAnswer
from app.services.clinical_text import normalize_search_text


def select_presentation(answer: GroundedAnswer, *, question: str, intent: str,
                        result: dict | None = None) -> GroundedAnswer:
    result = result or {}
    urgency = str(result.get("urgency") or result.get("escalation_level") or "").upper()
    n = normalize_search_text(question)
    # Only a specifically bounded education answer may become brief. Neither
    # short input nor "answer briefly" can suppress a clinical safety field.
    if urgency in {"URGENT", "EMERGENCY", "CRITICAL"}:
        mode = "focused"
    elif any(x in n for x in ("chi tiet", "giai thich ky", "phan tich", "cu the")):
        mode = "detailed"
    elif (intent == "general" and answer.presentation == "brief"
          and not answer.requires_human_review and not answer.questions
          and not answer.next_steps and not answer.key_points):
        mode = "brief"
    else:
        mode = "focused"
    updates = {'presentation': mode}
    if mode == 'focused' and intent == 'triage' and urgency == 'ROUTINE':
        # The causal explanation remains intact in summary/narrative and details.
        # Show the main point plus uncertainty, rather than a mechanism essay.
        first = re.split(r'(?<=[.!?])\s+', answer.summary.strip(), maxsplit=1)[0]
        if len(answer.summary.split()) > 70:
            updates['display_summary'] = first + ' Chưa thể xác định nguyên nhân chỉ từ tin nhắn; xem hướng chăm sóc và dấu hiệu cảnh báo bên dưới.'
        # Only this narrowly bounded simple question may collapse optional
        # self-care. Keep follow-up and every safety note visible. Compound
        # symptoms, drugs, additional history and emergencies do not match.
        if re.fullmatch(r'(?:toi\s+)?dau dau nhe sau khi nhin man hinh ca ngay[.!?]*', n):
            updates['display_next_steps'] = list(dict.fromkeys([*answer.next_steps[:2], *answer.next_steps[-1:]]))
    return answer.model_copy(update=updates)
