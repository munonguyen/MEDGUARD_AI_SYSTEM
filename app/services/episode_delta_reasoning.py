"""Episode-delta reasoning priority for V27.1 patient explanations.

The base contextual reasoner intentionally keeps earlier episode evidence so a
multi-turn conversation does not lose context. That memory is useful, but it
must not let a low-risk hypothesis from an earlier turn remain the leading
patient explanation after the latest turn adds higher-risk cardiorespiratory
features.

This adapter is deliberately narrow: it does not change Safety Kernel urgency,
create a diagnosis, or remove prior evidence. It fills the bounded chest
explanation gap, re-ranks explanations when new warning features appear, and
keeps a prior emergency explanation leading when symptoms only improve
transiently without a factual retraction of the warning features.
"""

from __future__ import annotations

import re
from types import ModuleType
from typing import Any

from app.models.clinical_reasoning import MechanismHypothesis
from app.services.clinical_text import normalize_search_text


_MARKER = "_v27_episode_delta_priority_installed"


def _current_turn_text(episode: Any) -> str:
    raw = str(getattr(episode, "latest_user_message", "") or "").strip()
    lowered = raw.lower()
    marker = "lượt hiện tại:"
    if marker in lowered:
        pos = lowered.rfind(marker)
        return raw[pos + len(marker):].strip()
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
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
    return " ".join(value for value in values if value).strip()


def _chest_context(text: str) -> bool:
    norm = normalize_search_text(text)
    return bool(re.search(r"\b(?:nguc|co nguc|thanh nguc|xuong suon|bo suon)\b", norm))


def _mechanical_chest_pattern(text: str) -> bool:
    norm = normalize_search_text(text)
    post_load = bool(re.search(r"\b(?:sau tap|tap gym|tap nguc|nang ta|day nguc|van dong manh)\b", norm))
    reproducible = bool(re.search(r"\b(?:an vao.*dau|dau khi an|so vao.*dau|xoay nguoi.*dau|co co.*dau)\b", norm))
    return _chest_context(norm) and post_load and reproducible


def _latest_risk_features(message: str) -> tuple[str, ...]:
    text = normalize_search_text(message)
    features: list[str] = []

    pressure = bool(
        re.search(
            r"\b(?:nang|ep|de|nghet|tuc)\s*(?:o\s*)?nguc\b|\bnguc\s*(?:nang|ep|de|nghet|tuc)\b",
            text,
        )
    )
    dyspnea = bool(re.search(r"\b(?:kho tho|hut hoi|thieu hoi)\b", text))
    exertion = bool(re.search(r"\b(?:gang suc|di bo nhanh|leo cau thang|tap the duc|van dong)\b", text))
    radiation = bool(re.search(r"\b(?:lan|dau lan).*\b(?:tay trai|canh tay|ham|lung|vai)\b", text))
    autonomic = bool(re.search(r"\b(?:va mo hoi|toat mo hoi|buon non|non|choang|ngat)\b", text))

    if pressure:
        features.append("chest_pressure")
    if dyspnea:
        features.append("dyspnea")
    if exertion and (pressure or dyspnea):
        features.append("exertional_relation")
    if radiation:
        features.append("radiation")
    if autonomic:
        features.append("autonomic_features")
    return tuple(features)


def _meaningful_risk(features: tuple[str, ...]) -> bool:
    return (
        "exertional_relation" in features
        or "radiation" in features
        or "autonomic_features" in features
        or ("chest_pressure" in features and "dyspnea" in features)
    )


def _mechanical_mechanism(message: str) -> MechanismHypothesis:
    return MechanismHypothesis(
        hypothesis_id="chest_wall_mechanical",
        label="Cơ hoặc thành ngực có thể góp phần vào cảm giác đau",
        role="leading",
        support_level="plausible",
        mechanism=(
            "Đau xuất hiện sau vận động cơ và tăng khi ấn trực tiếp phù hợp hơn với kích thích hoặc quá tải cơ–xương "
            "thành ngực, vì mô cơ và mô quanh xương sườn có thể đau rõ hơn khi bị ấn hoặc co kéo."
        ),
        evidence_for=(message,) if message.strip() else (),
        patient_safe_statement=(
            "Đặc điểm sau tập và đau tăng khi ấn làm nguyên nhân từ cơ/thành ngực hợp lý hơn, nhưng riêng dấu hiệu ấn đau "
            "không đủ để loại trừ nguyên nhân tim hoặc phổi nếu xuất hiện triệu chứng cảnh báo khác."
        ),
    )


def _warning_mechanism(message: str, features: tuple[str, ...], urgency: str) -> MechanismHypothesis:
    evidence = (message,) if message.strip() else ()
    high_risk_cluster = any(value in features for value in ("radiation", "autonomic_features"))
    if high_risk_cluster or urgency == "EMERGENCY":
        statement = (
            "Các dấu hiệu mới ở lượt hiện tại làm nguyên nhân tim–phổi nguy hiểm trở thành hướng cần ưu tiên đánh giá; "
            "đặc điểm đau cơ/thành ngực ở lượt trước không đủ để giải thích an toàn cho toàn bộ diễn tiến mới."
        )
        mechanism = (
            "Khi tim hoặc phổi không đáp ứng đủ nhu cầu oxy, người bệnh có thể xuất hiện đau hoặc nặng ngực, khó thở "
            "và phản ứng thần kinh tự chủ như vã mồ hôi, buồn nôn hoặc choáng. Những dấu hiệu này không tự xác nhận một "
            "chẩn đoán cụ thể nhưng đủ quan trọng để ưu tiên đánh giá cấp cứu."
        )
        label = "Dấu hiệu mới làm tăng ưu tiên cho bệnh cảnh tim–phổi nguy hiểm"
    else:
        statement = (
            "Việc nặng/đau ngực hoặc khó thở xuất hiện rõ khi gắng sức làm ngưỡng cảnh giác tim–phổi cao hơn so với "
            "một cơn đau chỉ liên quan ấn hoặc vận động cơ."
        )
        mechanism = (
            "Gắng sức làm nhu cầu oxy của cơ thể tăng. Nếu khó chịu ngực hoặc khó thở tăng theo mức gắng sức, cần xem xét "
            "khả năng tim–phổi không đáp ứng đủ nhu cầu đó thay vì quy toàn bộ triệu chứng cho cơ thành ngực."
        )
        label = "Triệu chứng theo gắng sức làm tăng ưu tiên đánh giá tim–phổi"

    return MechanismHypothesis(
        hypothesis_id="episode_delta_cardiorespiratory_warning",
        label=label,
        role="leading",
        support_level="supported",
        mechanism=mechanism,
        evidence_for=evidence,
        patient_safe_statement=statement,
    )


def _historical_emergency_mechanism(evidence_text: str) -> MechanismHypothesis:
    return MechanismHypothesis(
        hypothesis_id="historical_cardiorespiratory_emergency",
        label="Dấu hiệu cảnh báo tim–phổi trước đó vẫn có giá trị dù triệu chứng tạm giảm",
        role="leading",
        support_level="supported",
        mechanism=(
            "Một số bệnh cảnh tim–phổi cấp có thể dao động hoặc giảm tạm thời khi nghỉ. Việc cơn đau hay khó chịu đỡ đi "
            "không chứng minh rằng nguy cơ đã hết; khi trước đó đã có nặng/đau ngực theo gắng sức, khó thở, đau lan hoặc "
            "vã mồ hôi/buồn nôn, mức cấp cứu vẫn phải được giữ cho tới khi được đánh giá trực tiếp."
        ),
        evidence_for=(evidence_text,) if evidence_text.strip() else (),
        patient_safe_statement=(
            "Việc bạn thấy đỡ sau khi nghỉ không xóa các dấu hiệu cảnh báo tim–phổi đã xuất hiện trước đó; vì vậy không "
            "nên dùng sự cải thiện tạm thời để hạ mức cấp cứu."
        ),
    )


def _with_mechanical_baseline(frame: Any, episode: Any) -> Any:
    mechanisms = list(tuple(getattr(frame, "mechanisms", ()) or ()))
    if mechanisms:
        return frame
    full_text = _episode_text(episode)
    if not _mechanical_chest_pattern(full_text):
        return frame

    current = _current_turn_text(episode)
    mechanism = _mechanical_mechanism(current or full_text)
    return frame.model_copy(
        update={
            "mechanisms": (mechanism,),
            "leading_hypothesis_ids": (mechanism.hypothesis_id,),
            "next_best_question": (
                "Cơn đau chỉ xuất hiện khi ấn hoặc cử động vùng ngực, hay bạn cũng thấy nặng/ép ngực khi đi nhanh hoặc leo cầu thang?"
            ),
            "next_question_key": "exertional_relation",
        }
    )


def _promote_mechanism(frame: Any, mechanism: MechanismHypothesis, *, emergency: bool) -> Any:
    updated: list[MechanismHypothesis] = [mechanism]
    for existing in tuple(getattr(frame, "mechanisms", ()) or ()):
        if existing.hypothesis_id == mechanism.hypothesis_id:
            continue
        if existing.role == "leading":
            existing = existing.model_copy(update={"role": "contributor"})
        updated.append(existing)

    update: dict[str, Any] = {
        "mechanisms": tuple(updated),
        "leading_hypothesis_ids": (mechanism.hypothesis_id,),
    }
    if emergency:
        update["next_best_question"] = None
        update["next_question_key"] = None
    return frame.model_copy(update=update)


def _reprioritize_frame(frame: Any, episode: Any, urgency: str) -> Any:
    frame = _with_mechanical_baseline(frame, episode)
    current = _current_turn_text(episode)
    full_text = _episode_text(episode)
    if not _chest_context(full_text):
        return frame

    urgency_value = str(urgency or "ROUTINE").upper()
    current_features = _latest_risk_features(current)
    if _meaningful_risk(current_features):
        warning = _warning_mechanism(current, current_features, urgency_value)
        return _promote_mechanism(frame, warning, emergency=urgency_value == "EMERGENCY")

    # Risk memory is explanation memory too. If Safety Kernel still holds an
    # emergency floor and the active episode explicitly contains the warning
    # features that created it, a later report of temporary improvement must not
    # make an earlier benign chest-wall hypothesis leading again.
    episode_features = _latest_risk_features(full_text)
    if urgency_value == "EMERGENCY" and _meaningful_risk(episode_features):
        historical = _historical_emergency_mechanism(full_text)
        return _promote_mechanism(frame, historical, emergency=True)

    return frame


def install_episode_delta_reasoning(reasoner_module: ModuleType) -> None:
    """Patch the public frame builder after the base reasoner has loaded."""

    if getattr(reasoner_module, _MARKER, False):
        return
    original = getattr(reasoner_module, "build_contextual_reasoning_frame", None)
    if original is None:
        return

    def build_contextual_reasoning_frame(episode: Any, *, urgency: str = "ROUTINE") -> Any:
        frame = original(episode, urgency=urgency)
        return _reprioritize_frame(frame, episode, urgency)

    reasoner_module.build_contextual_reasoning_frame = build_contextual_reasoning_frame
    setattr(reasoner_module, _MARKER, True)
