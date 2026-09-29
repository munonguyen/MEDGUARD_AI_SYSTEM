"""V25 clinical episode construction.

This layer sits *above* the frozen semantic fact parser and event ledger.  It
never invents a diagnosis or changes urgency.  Its job is to turn multi-turn
facts into a writer-facing story model with a strict distinction between:

- confirmed positive findings,
- explicitly confirmed negative findings,
- decision-relevant unknowns, and
- historical risks that must not disappear when symptoms improve.

The central invariant is: NOT MENTIONED != NEGATIVE.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Sequence

from app.models.clinical_episode import (
    ClinicalEpisodeModel,
    DecisionUnknown,
    EpisodeDelta,
    EpisodeFact,
)
from app.models.clinical_events import ClinicalEvent, ClinicalFactSet
from app.services.clinical_event_ledger import ClinicalEventLedger, LedgerEventStatus
from app.services.clinical_fact_parser import parse_semantic_clinical_facts
from app.services.clinical_text import normalize_search_text
from app.services.risk_memory import infer_episode_domain, should_start_new_episode


_HARD_CONSEQUENCES = {
    "catastrophic_vascular_threat",
    "limb_perfusion_failure",
    "peritoneal_irritation",
    "circulatory_compromise",
    "neuromuscular_airway_compromise",
    "retinal_or_optic_ischemia",
    "acute_toxic_metabolic_threat",
    "exsanguinating_hemorrhage",
    "metabolic_crisis",
}


@dataclass(frozen=True)
class _UnknownSpec:
    key: str
    question: str
    impact: str
    changes: tuple[str, ...]
    rationale: str
    patterns: tuple[str, ...]


_COMMON_UNKNOWN_SPECS: tuple[_UnknownSpec, ...] = (
    _UnknownSpec(
        key="onset_speed",
        question="Triệu chứng xuất hiện từ từ hay khởi phát đột ngột và đạt mức nặng trong vài phút?",
        impact="critical",
        changes=("emergency_disposition", "leading_interpretation"),
        rationale="Tốc độ khởi phát có thể phân biệt một bệnh cảnh thông thường với biến cố cấp cần xử trí ngay.",
        patterns=(
            r"\b(dot ngot|bong nhien|tu nhien|nhu set danh|trong vai phut|tu tu|dan dan|am i|keo dai)\b",
        ),
    ),
    _UnknownSpec(
        key="trajectory",
        question="Từ lúc bắt đầu đến giờ triệu chứng đang tăng lên, giảm đi hay gần như giữ nguyên?",
        impact="high",
        changes=("urgency", "self_care_vs_evaluation"),
        rationale="Diễn tiến theo thời gian quyết định liệu theo dõi tại nhà còn phù hợp hay cần đánh giá trực tiếp.",
        patterns=(
            r"\b(tang dan|nang hon|te hon|giam|do hon|bot|khong doi|van nhu cu|giu nguyen)\b",
        ),
    ),
)


_DOMAIN_UNKNOWN_SPECS: dict[str, tuple[_UnknownSpec, ...]] = {
    "neurovestibular": (
        _UnknownSpec(
            key="focal_neurologic_deficit",
            question="Bạn có yếu hoặc tê một bên người, méo miệng, nói khó hay đi đứng mất thăng bằng mới xuất hiện không?",
            impact="critical",
            changes=("emergency_disposition", "neurologic_pathway"),
            rationale="Thiếu sót thần kinh khu trú mới xuất hiện có thể làm thay đổi ngay mức xử trí.",
            patterns=(r"\b(yeu tay|yeu chan|yeu nua nguoi|te nua nguoi|meo mieng|noi ngong|kho noi|mat thang bang|khong yeu|khong te)\b",),
        ),
        _UnknownSpec(
            key="fever_neck_stiffness",
            question="Bạn có sốt kèm cứng gáy, rất sợ ánh sáng hoặc lơ mơ hơn bình thường không?",
            impact="critical",
            changes=("emergency_disposition", "infection_pathway"),
            rationale="Sốt kèm cứng gáy hoặc thay đổi ý thức là nhóm dữ kiện cần ưu tiên loại trừ trong đau đầu cấp.",
            patterns=(r"\b(sot|khong sot|cung gay|khong cung gay|so anh sang|lo mo|tinh tao)\b",),
        ),
        _UnknownSpec(
            key="head_trauma",
            question="Gần đây bạn có bị ngã, va đập hoặc chấn thương vùng đầu không?",
            impact="high",
            changes=("imaging_or_evaluation",),
            rationale="Chấn thương đầu làm thay đổi ngưỡng đánh giá một cơn đau đầu mới.",
            patterns=(r"\b(chan thuong dau|va dau|dap dau|nga|khong bi nga|khong va dap)\b",),
        ),
        _UnknownSpec(
            key="visual_loss",
            question="Bạn có mất hoặc giảm thị lực mới xuất hiện, nhìn đôi hay thấy màn che trước mắt không?",
            impact="high",
            changes=("urgent_eye_or_neurologic_evaluation",),
            rationale="Thay đổi thị lực mới xuất hiện có thể chỉ sang nhóm nguyên nhân cần đánh giá sớm hơn.",
            patterns=(r"\b(mat thi luc|giam thi luc|mo mat|nhin doi|man che|nhin binh thuong|khong mo mat)\b",),
        ),
    ),
    "cardiorespiratory": (
        _UnknownSpec(
            key="exertional_relation",
            question="Cảm giác khó chịu có xuất hiện hoặc tăng lên khi đi bộ nhanh, leo cầu thang hay gắng sức không?",
            impact="high",
            changes=("cardiac_risk", "urgency"),
            rationale="Mối liên hệ với gắng sức có thể thay đổi đáng kể cách đánh giá đau hoặc nặng ngực.",
            patterns=(r"\b(gang suc|di bo nhanh|leo cau thang|tap the duc|khi nghi|luc nghi)\b",),
        ),
        _UnknownSpec(
            key="radiation_autonomic",
            question="Đau có lan ra tay, vai, hàm hoặc lưng và kèm vã mồ hôi, buồn nôn không?",
            impact="critical",
            changes=("emergency_disposition", "cardiac_pathway"),
            rationale="Đau lan kèm triệu chứng thần kinh thực vật là dữ kiện có thể làm tăng mạnh mức cảnh giác tim mạch.",
            patterns=(r"\b(lan tay|lan vai|lan ham|lan lung|va mo hoi|buon non|khong lan|khong va mo hoi)\b",),
        ),
        _UnknownSpec(
            key="dyspnea_syncope",
            question="Bạn có khó thở rõ, choáng muốn ngất hoặc đã ngất trong cơn này không?",
            impact="critical",
            changes=("emergency_disposition",),
            rationale="Khó thở hoặc mất ý thức trong bệnh cảnh ngực là dữ kiện ưu tiên cao cho phân luồng.",
            patterns=(r"\b(kho tho|hut hoi|ngat|sap ngat|khong kho tho|khong ngat)\b",),
        ),
    ),
    "gastrointestinal": (
        _UnknownSpec(
            key="pain_location_migration",
            question="Đau tập trung ở vị trí nào, và có chuyển từ vị trí này sang vị trí khác không?",
            impact="high",
            changes=("surgical_abdomen_probability", "specialty"),
            rationale="Vị trí và sự di chuyển của đau bụng giúp phân biệt nhiều cơ chế bệnh lý khác nhau.",
            patterns=(r"\b(quanh ron|ha suon|thuong vi|bung duoi|ben phai|ben trai|chuyen xuong|di chuyen)\b",),
        ),
        _UnknownSpec(
            key="peritoneal_signs",
            question="Bụng có cứng, đau tăng rõ khi ấn hoặc khi di chuyển, ho hay hít sâu không?",
            impact="critical",
            changes=("emergency_disposition", "surgical_pathway"),
            rationale="Bụng cứng hoặc đau kiểu kích thích phúc mạc có thể làm thay đổi ngay mức xử trí.",
            patterns=(r"\b(bung cung|co cung|dau khi an|an dau|dau khi di chuyen|bung mem)\b",),
        ),
        _UnknownSpec(
            key="bleeding_or_dehydration",
            question="Bạn có nôn ra máu, đi ngoài phân đen/ra máu, nôn liên tục hoặc choáng khi đứng lên không?",
            impact="critical",
            changes=("emergency_disposition", "fluid_or_bleeding_pathway"),
            rationale="Chảy máu tiêu hóa hoặc mất nước nặng là các yếu tố làm thay đổi mức khẩn cấp.",
            patterns=(r"\b(non ra mau|phan den|di ngoai ra mau|non lien tuc|choang khi dung|khong non|phan binh thuong)\b",),
        ),
    ),
    "musculoskeletal_spine": (
        _UnknownSpec(
            key="motor_sensory_deficit",
            question="Bạn có yếu chân, tê tăng dần hoặc khó nhấc bàn chân mới xuất hiện không?",
            impact="high",
            changes=("urgent_neurologic_evaluation",),
            rationale="Thiếu sót vận động hoặc cảm giác mới xuất hiện làm thay đổi cách đánh giá đau lưng/cột sống.",
            patterns=(r"\b(yeu chan|te chan|khong nhac duoc ban chan|foot drop|khong yeu|khong te)\b",),
        ),
        _UnknownSpec(
            key="cauda_equina_features",
            question="Bạn có tê vùng quanh hậu môn/sinh dục hoặc mới khó kiểm soát tiểu tiện, đại tiện không?",
            impact="critical",
            changes=("emergency_disposition", "spinal_emergency_pathway"),
            rationale="Rối loạn cơ tròn hoặc tê vùng yên ngựa là nhóm dấu hiệu không được bỏ sót trong đau lưng.",
            patterns=(r"\b(te vung yen ngua|te quanh hau mon|te sinh duc|bi tieu|khong kiem soat tieu|khong roi loan tieu)\b",),
        ),
    ),
    "dermatology": (
        _UnknownSpec(
            key="airway_mucosal_involvement",
            question="Bạn có sưng môi/lưỡi, nghẹn cổ, khàn tiếng hoặc khó thở không?",
            impact="critical",
            changes=("emergency_disposition", "anaphylaxis_pathway"),
            rationale="Triệu chứng đường thở hoặc niêm mạc có thể biến một phản ứng da thành cấp cứu.",
            patterns=(r"\b(sung moi|sung luoi|nghen co|khan tieng|kho tho|khong sung moi|tho binh thuong)\b",),
        ),
        _UnknownSpec(
            key="new_exposure",
            question="Ngay trước khi nổi ban bạn có dùng thuốc, ăn món lạ hoặc tiếp xúc sản phẩm/hóa chất mới nào không?",
            impact="high",
            changes=("exposure_hypothesis", "avoidance_advice"),
            rationale="Mối liên hệ thời gian với một phơi nhiễm mới giúp xác định hướng phản ứng dị ứng/tiếp xúc.",
            patterns=(r"\b(thuoc moi|mon la|thuc an moi|my pham moi|hoa chat|sau khi uong|sau khi an|khong co gi moi)\b",),
        ),
    ),
}


def _message_parts(message: Any) -> tuple[str | None, str]:
    if isinstance(message, dict):
        return message.get("role"), str(message.get("content") or "")
    return getattr(message, "role", None), str(getattr(message, "content", "") or "")


def _event_fact(event: ClinicalEvent, turn_index: int, polarity: str) -> EpisodeFact:
    return EpisodeFact(
        concept=event.concept,
        polarity=polarity,
        organ_system=event.organ_system,
        body_site=event.body_site,
        onset=getattr(event.onset, "value", str(event.onset)) if event.onset else None,
        severity=getattr(event.severity, "value", str(event.severity)) if event.severity else None,
        evidence_span=event.evidence_span or event.concept,
        source_turn=turn_index,
        temporality=event.temporality,
    )


def _dedupe_facts(facts: Iterable[EpisodeFact]) -> tuple[EpisodeFact, ...]:
    latest: dict[tuple[str, str], EpisodeFact] = {}
    for fact in facts:
        latest[(fact.concept, fact.polarity)] = fact
    return tuple(sorted(latest.values(), key=lambda item: (item.source_turn, item.concept)))


def _answered(text: str, spec: _UnknownSpec) -> bool:
    normalized = normalize_search_text(text)
    return any(re.search(pattern, normalized) for pattern in spec.patterns)


def _unknowns(domain: str | None, active_text: str) -> tuple[DecisionUnknown, ...]:
    specs = [*_COMMON_UNKNOWN_SPECS, *_DOMAIN_UNKNOWN_SPECS.get(domain or "", ())]
    values: list[DecisionUnknown] = []
    seen: set[str] = set()
    for spec in specs:
        if spec.key in seen or _answered(active_text, spec):
            continue
        seen.add(spec.key)
        values.append(
            DecisionUnknown(
                key=spec.key,
                question=spec.question,
                impact=spec.impact,
                changes=spec.changes,
                rationale=spec.rationale,
            )
        )
    impact_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    values.sort(key=lambda item: (impact_rank[item.impact], item.key))
    return tuple(values)


def _problem_representation(domain: str | None, positives: Sequence[EpisodeFact], latest: str) -> str:
    concepts = [fact.concept for fact in positives[-5:]]
    fact_text = ", ".join(dict.fromkeys(concepts)) if concepts else "chưa trích xuất được dấu hiệu có cấu trúc"
    domain_text = domain or "clinical_problem"
    return f"{domain_text}: {fact_text}; lời kể mới nhất: {latest.strip()[:180]}"


def build_clinical_episode_model(
    *,
    episode_id: str,
    messages: Sequence[Any],
) -> ClinicalEpisodeModel:
    user_turns = [content.strip() for role, content in map(_message_parts, messages) if role == "user" and content.strip()]
    if not user_turns:
        raise ValueError("clinical episode requires at least one user turn")

    ledger = ClinicalEventLedger(episode_id=episode_id)
    active_fact_sets: list[tuple[int, ClinicalFactSet]] = []
    active_texts: list[str] = []
    previous_text: str | None = None
    episode_switched = False
    active_domain: str | None = None

    for turn_index, text in enumerate(user_turns, 1):
        if previous_text and should_start_new_episode(text, previous_text):
            active_fact_sets = []
            active_texts = []
            episode_switched = True
            active_domain = None
        fact_set = parse_semantic_clinical_facts(text)
        ledger.process_turn(turn_index, text, fact_set)
        active_fact_sets.append((turn_index, fact_set))
        active_texts.append(text)
        active_domain = infer_episode_domain(text) or active_domain
        previous_text = text

    positives: list[EpisodeFact] = []
    negatives: list[EpisodeFact] = []
    for turn_index, fact_set in active_fact_sets:
        positives.extend(_event_fact(event, turn_index, "present") for event in fact_set.present_events)
        negatives.extend(_event_fact(event, turn_index, "absent") for event in fact_set.negated_events)

    positive_facts = _dedupe_facts(positives)
    negative_facts = _dedupe_facts(negatives)
    latest_turn_index, latest_fact_set = active_fact_sets[-1]
    latest_positive = tuple(event.concept for event in latest_fact_set.present_events)
    latest_negative = tuple(event.concept for event in latest_fact_set.negated_events)

    historical: list[EpisodeFact] = []
    for entry in ledger.entries:
        if entry.status == LedgerEventStatus.INVALIDATED:
            continue
        event = entry.event
        is_prior = entry.turn_index < latest_turn_index
        is_historical = entry.status == LedgerEventStatus.HISTORICALLY_CONFIRMED
        is_hard = event.is_critical or event.physiologic_consequence in _HARD_CONSEQUENCES
        if is_historical or (is_prior and is_hard):
            historical.append(_event_fact(event, entry.turn_index, "present"))
    historical_facts = _dedupe_facts(historical)

    active_text = "\n".join(active_texts)
    coverage_values = [fact_set.semantic_coverage for _, fact_set in active_fact_sets]
    semantic_coverage = sum(coverage_values) / len(coverage_values) if coverage_values else 0.0
    historical_concepts = tuple(fact.concept for fact in historical_facts)

    return ClinicalEpisodeModel(
        episode_id=episode_id,
        chief_domain=active_domain,
        latest_user_message=user_turns[-1],
        problem_representation=_problem_representation(active_domain, positive_facts, user_turns[-1]),
        confirmed_positive=positive_facts,
        confirmed_negative=negative_facts,
        unknown_decision_relevant=_unknowns(active_domain, active_text),
        historical_risk=historical_facts,
        delta=EpisodeDelta(
            new_positive=latest_positive,
            new_negative=latest_negative,
            new_historical_risk=historical_concepts,
            episode_switched=episode_switched,
        ),
        semantic_coverage=round(semantic_coverage, 4),
        user_turns_in_active_episode=len(active_fact_sets),
        has_hard_historical_risk=bool(historical_facts),
    )
