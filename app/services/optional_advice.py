"""Optional presentation of existing, bounded routine self-care facts.

Never synthesizes treatment, moves mandatory actions, or relabels safety instructions.
"""
import re
from app.models.chat import GroundedAnswer

_UNSAFE_OPTIONAL = re.compile(r'\d|thuốc|kháng sinh|liều|không |ngừng|dừng|tránh|cấp cứu|bác sĩ|khám|dược sĩ|gọi|chẩn đoán|điều trị|medication|dose|emergency', re.I)


def attach_optional_advice(answer: GroundedAnswer, payload: dict, urgency: str) -> GroundedAnswer:
    # Fail closed for unknown acuity and every safety escalation.
    values = []
    if urgency.upper() == 'ROUTINE' and not payload.get('emergency_flag'):
        self_care = payload.get('self_care', [])
        if isinstance(self_care, list):
            for item in self_care:
                text = str(item).strip()
                if 10 <= len(text) <= 240 and not _UNSAFE_OPTIONAL.search(text) and text not in values:
                    values.append(text)
    return answer.model_copy(update={'optional_advice': values[:2]})
