"""Episode-delta reasoning priority for V27.1 patient explanations.

The base contextual reasoner intentionally keeps earlier episode evidence so a
multi-turn conversation does not lose context. That memory is useful, but it
must not let a low-risk hypothesis from an earlier turn remain the leading
patient explanation after the latest turn adds higher-risk cardiorespiratory
features.

This adapter is deliberately narrow: it does not change Safety Kernel urgency,
create a diagnosis, or remove prior evidence. It only re-ranks explanation
hypotheses when the *latest* user message contains explicit features that make a
cardiorespiratory pathway more decision-relevant than an earlier chest-wall
pattern.
"""

from __future__ import annotations

import re
from types import ModuleType
from typing import Any

from app.models.clinical_reasoning import MechanismHypothesis
from app.services.clinical_text import normalize_search_text


_MARKER = "_v27_episode_delta_priority_installed"


def _latest_risk_features(message: str) -> tuple[str, ...]:
    text = normalize_search_text(message)
    features: list[str] = []

    pressure = bool(re.search(r"\b(?:nang|ep|de|nghet|tuc)\s*(?:o\s*)?nguc\b|\bnguc\s*(?:nang|ep|de|nghet|tuc)\b", text))
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


def _reprioritize_frame(frame: Any, episode: Any, urgency: str) -> Any:
    if getattr(episode, "chief_domain", None) != "cardiorespiratory":
        return frame

    latest = str(getattr(episode, "latest_user_message", "") or "")
    features = _latest_risk_features(latest)
    urgency_value = str(urgency or "ROUTINE").upper()
    if not features and urgency_value == "ROUTINE":
        return frame

    # Do not escalate explanation priority solely from an inherited urgency when
    # the current message contains no cardiorespiratory warning feature. Sticky
    # emergency memory is preserved by Safety Kernel; this layer only explains
    # explicit episode delta.
    if not features:
        return frame

    meaningful_risk = (
        "exertional_relation" in features
        or "radiation" in features
        or "autonomic_features" in features
        or ("chest_pressure" in features and "dyspnea" in features)
    )
    if not meaningful_risk:
        return frame

    warning = _warning_mechanism(latest, features, urgency_value)
    updated: list[MechanismHypothesis] = [warning]
    for mechanism in tuple(getattr(frame, "mechanisms", ()) or ()):
        if mechanism.hypothesis_id == warning.hypothesis_id:
            continue
        if mechanism.hypothesis_id == "chest_wall_mechanical" and mechanism.role == "leading":
            mechanism = mechanism.model_copy(update={"role": "contributor"})
        elif mechanism.role == "leading":
            mechanism = mechanism.model_copy(update={"role": "contributor"})
        updated.append(mechanism)

    return frame.model_copy(
        update={
            "mechanisms": tuple(updated),
            "leading_hypothesis_ids": (warning.hypothesis_id,),
        }
    )


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
