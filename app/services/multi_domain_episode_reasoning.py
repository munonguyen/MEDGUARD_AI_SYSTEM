"""V27.2 multi-domain episode-delta reasoning.

Chest-pain delta handling exists in ``episode_delta_reasoning``. This module
extends the same invariant to neurologic headache/stroke patterns and spinal
neurologic warning patterns: a newly introduced red flag must become the leading
explanation and an earlier benign mechanism may remain only as a contributor.

This is explanation prioritisation only. Safety Kernel owns urgency.
"""

from __future__ import annotations

import re
from types import ModuleType
from typing import Any

from app.models.clinical_reasoning import MechanismHypothesis
from app.services.clinical_text import normalize_search_text


_MARKER = "_v27_2_multi_domain_priority_installed"
_HEADACHE_MECHANISM_IDS = {
    "visual_load_contribution",
    "postural_pericranial_tension",
    "headache_threshold_modifiers",
    "secondary_headache_safety_pathway",
}


def _current_turn(episode: Any) -> str:
    raw = str(getattr(episode, "latest_user_message", "") or "").strip()
    lowered = raw.lower()
    marker = "lượt hiện tại:"
    if marker in lowered:
        pos = lowered.rfind(marker)
        return raw[pos + len(marker):].strip()
    lines = [value.strip() for value in raw.splitlines() if value.strip()]
    return lines[-1] if lines else raw


def _episode_text(episode: Any) -> str:
    values = [
        str(getattr(episode, "active_episode_text", "") or ""),
        str(getattr(episode, "latest_user_message", "") or ""),
    ]
    for fact in tuple(getattr(episode, "confirmed_positive", ()) or ()):
        span = str(getattr(fact, "evidence_span", "") or "")
        if span:
            values.append(span)
    return " ".join(values)


def _improvement(text: str) -> bool:
    norm = normalize_search_text(text)
    return bool(
        re.search(
            r"\b(?:do hon|bot hon|giam dau|do dau|het dau|nghi.*do|tam thoi do|noi ro hon|cam thay do)\b",
            norm,
        )
    )


def _neuro_features(text: str) -> tuple[str, ...]:
    norm = normalize_search_text(text)
    features: list[str] = []
    thunderclap = (
        ("dot ngot" in norm and any(value in norm for value in ("du doi", "dau dau", "set danh")))
        or "du doi nhat tu truoc toi gio" in norm
        or "dau dau set danh" in norm
    )
    focal = bool(
        re.search(
            r"\b(?:meo mieng|lech mieng|noi ngong|kho noi|yeu tay|yeu chan|yeu nua nguoi|te nua nguoi|mat thi luc|nhin mo dot ngot)\b",
            norm,
        )
    )
    seizure_or_syncope = bool(re.search(r"\b(?:co giat|ngat xiu|hon me|mat y thuc)\b", norm))
    if thunderclap:
        features.append("thunderclap")
    if focal:
        features.append("focal_neurologic_deficit")
    if seizure_or_syncope:
        features.append("altered_consciousness")
    return tuple(features)


def _spine_features(text: str) -> tuple[str, ...]:
    norm = normalize_search_text(text)
    features: list[str] = []
    weakness = bool(
        re.search(
            r"\b(?:yeu chan|chan yeu|kho nhac ban chan|khong nhac duoc ban chan|sup ban chan|foot drop)\b",
            norm,
        )
    )
    saddle = bool(
        re.search(
            r"\b(?:te vung yen ngua|te quanh hau mon|te quanh sinh duc|te vung quanh mong|mat cam giac vung hoi am)\b",
            norm,
        )
    )
    bladder = bool(
        re.search(
            r"\b(?:kho kiem soat tieu tien|tieu khong tu chu|bi tieu|khong tieu duoc|bi dai tien|dai tien khong tu chu)\b",
            norm,
        )
    )
    if weakness:
        features.append("new_leg_weakness")
    if saddle:
        features.append("saddle_sensory_change")
    if bladder:
        features.append("bladder_bowel_change")
    return tuple(features)


def _neuro_warning(evidence: str, *, historical: bool) -> MechanismHypothesis:
    if historical:
        statement = (
            "Việc triệu chứng có giảm tạm thời không xóa các dấu hiệu thần kinh cảnh báo đã xuất hiện trước đó; "
            "mức xử trí vẫn phải dựa trên đỉnh nguy cơ của toàn bộ cơn."
        )
        mechanism = (
            "Một số tình trạng thần kinh cấp có thể dao động hoặc cải thiện tạm thời. Vì vậy, khi trước đó đã có đau đầu "
            "đột ngột dữ dội, yếu liệt, nói khó, ngất hoặc co giật, sự cải thiện ngắn không đủ để hạ mức cảnh giác."
        )
        hid = "historical_neurologic_emergency"
        label = "Dấu hiệu thần kinh cấp trước đó vẫn chi phối mức xử trí"
    else:
        statement = (
            "Dữ kiện mới ở lượt này thuộc nhóm dấu hiệu thần kinh cảnh báo và quan trọng hơn giả thuyết lành tính ở các lượt trước."
        )
        mechanism = (
            "Đau đầu khởi phát đột ngột rất dữ dội hoặc xuất hiện cùng yếu liệt, nói khó, rối loạn ý thức hay co giật "
            "có thể phản ánh một biến cố thần kinh cấp cần được đánh giá ngay; không nên quy diễn tiến này cho mỏi mắt hoặc căng cơ."
        )
        hid = "episode_delta_neurologic_warning"
        label = "Dấu hiệu mới làm tăng ưu tiên đánh giá thần kinh cấp"
    return MechanismHypothesis(
        hypothesis_id=hid,
        label=label,
        role="leading",
        support_level="supported",
        mechanism=mechanism,
        evidence_for=(evidence,) if evidence.strip() else (),
        patient_safe_statement=statement,
    )


def _spine_warning(evidence: str, *, historical: bool) -> MechanismHypothesis:
    if historical:
        statement = (
            "Dù đau hoặc tê có giảm tạm thời, các dấu hiệu yếu chân hay rối loạn tiểu tiện/cảm giác vùng yên ngựa đã xuất hiện trước đó "
            "vẫn là cảnh báo thần kinh cần giữ mức xử trí khẩn cấp."
        )
        mechanism = (
            "Triệu chứng chèn ép hoặc tổn thương thần kinh có thể dao động. Sự cải thiện ngắn không đủ để loại trừ nguy cơ khi đã có "
            "yếu vận động, thay đổi cảm giác vùng hội âm hoặc rối loạn bàng quang/ruột."
        )
        hid = "historical_spinal_neurologic_emergency"
        label = "Dấu hiệu thần kinh cột sống trước đó vẫn chi phối mức xử trí"
    else:
        statement = (
            "Yếu chân mới xuất hiện, khó nhấc bàn chân hoặc thay đổi cảm giác vùng yên ngựa/kiểm soát tiểu tiện làm bệnh cảnh không còn phù hợp với đau cơ học đơn thuần."
        )
        mechanism = (
            "Những thay đổi vận động, cảm giác vùng hội âm hoặc chức năng bàng quang/ruột có thể cho thấy đường dẫn truyền thần kinh vùng cột sống đang bị ảnh hưởng, "
            "nên cần ưu tiên đánh giá cấp cứu thay vì tiếp tục giải thích bằng tư thế hoặc căng cơ."
        )
        hid = "episode_delta_spinal_neurologic_warning"
        label = "Dấu hiệu mới làm tăng ưu tiên đánh giá thần kinh cột sống"
    return MechanismHypothesis(
        hypothesis_id=hid,
        label=label,
        role="leading",
        support_level="supported",
        mechanism=mechanism,
        evidence_for=(evidence,) if evidence.strip() else (),
        patient_safe_statement=statement,
    )


def _replace_leading(frame: Any, warning: MechanismHypothesis, *, emergency: bool) -> Any:
    updated: list[MechanismHypothesis] = [warning]
    for mechanism in tuple(getattr(frame, "mechanisms", ()) or ()):
        if mechanism.hypothesis_id == warning.hypothesis_id:
            continue
        if mechanism.role == "leading":
            mechanism = mechanism.model_copy(update={"role": "contributor"})
        updated.append(mechanism)
    changes: dict[str, Any] = {
        "mechanisms": tuple(updated),
        "leading_hypothesis_ids": (warning.hypothesis_id,),
    }
    if emergency:
        changes["next_best_question"] = None
        changes["next_question_key"] = None
    return frame.model_copy(update=changes)


def _drop_headache_only_mechanisms(frame: Any) -> Any:
    """Prevent dizziness/eye complaints from inheriting headache-only prose."""
    mechanisms = tuple(
        mechanism
        for mechanism in tuple(getattr(frame, "mechanisms", ()) or ())
        if getattr(mechanism, "hypothesis_id", "") not in _HEADACHE_MECHANISM_IDS
    )
    leading = tuple(
        mechanism.hypothesis_id
        for mechanism in mechanisms
        if getattr(mechanism, "role", "") == "leading"
    )
    if mechanisms == tuple(getattr(frame, "mechanisms", ()) or ()):
        return frame
    return frame.model_copy(
        update={
            "mechanisms": mechanisms,
            "leading_hypothesis_ids": leading,
        }
    )


def _reprioritize(frame: Any, episode: Any, urgency: str) -> Any:
    domain = str(getattr(episode, "chief_domain", "") or "")
    urgency_value = str(urgency or "ROUTINE").upper()
    current = _current_turn(episode)
    full = _episode_text(episode)

    if domain == "neurovestibular":
        # The base V25 reasoner historically routed every neurovestibular
        # complaint through headache mechanisms. Dizziness, presyncope or eye
        # discomfort must not receive screen-strain/headache safety prose unless
        # headache is actually part of the active episode.
        if "dau dau" not in normalize_search_text(full):
            frame = _drop_headache_only_mechanisms(frame)

        current_features = _neuro_features(current)
        full_features = _neuro_features(full)
        if current_features:
            return _replace_leading(
                frame,
                _neuro_warning(current, historical=False),
                emergency=urgency_value == "EMERGENCY",
            )
        if urgency_value == "EMERGENCY" and full_features and _improvement(current):
            return _replace_leading(
                frame,
                _neuro_warning(full, historical=True),
                emergency=True,
            )

    if domain == "musculoskeletal_spine":
        current_features = _spine_features(current)
        full_features = _spine_features(full)
        current_critical = (
            "new_leg_weakness" in current_features
            or "saddle_sensory_change" in current_features
            or "bladder_bowel_change" in current_features
        )
        full_critical = (
            "new_leg_weakness" in full_features
            and (
                "saddle_sensory_change" in full_features
                or "bladder_bowel_change" in full_features
            )
        )
        if current_critical:
            return _replace_leading(
                frame,
                _spine_warning(current, historical=False),
                emergency=urgency_value == "EMERGENCY",
            )
        if urgency_value == "EMERGENCY" and full_critical and _improvement(current):
            return _replace_leading(
                frame,
                _spine_warning(full, historical=True),
                emergency=True,
            )

    return frame


def install_multi_domain_episode_reasoning(reasoner_module: ModuleType) -> None:
    if getattr(reasoner_module, _MARKER, False):
        return
    original = getattr(reasoner_module, "build_contextual_reasoning_frame", None)
    if original is None:
        return

    def build_contextual_reasoning_frame(episode: Any, *, urgency: str = "ROUTINE") -> Any:
        frame = original(episode, urgency=urgency)
        return _reprioritize(frame, episode, urgency)

    reasoner_module.build_contextual_reasoning_frame = build_contextual_reasoning_frame
    setattr(reasoner_module, _MARKER, True)