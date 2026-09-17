"""Unit tests for ClinicalEventLedger and Multi-Turn Risk Persistence (Gate 18).

Enforces 10 Critical Stress Scenarios:
1. T4 -> avoidance -> home question: Risk retained.
2. T4 -> symptom improvement: Risk retained.
3. T4 -> bare retraction: Valid retraction invalidates.
4. T4 -> valid correction: Objective factual correction invalidates.
5. T4 -> partial correction: Target-specific invalidation (toxicology retracted, chest pain retained).
6. T4 -> correction of unrelated fact: Danger retained.
7. T4 -> new episode: Episode isolation guaranteed.
8. T4 -> caregiver correction: Parent/caregiver device clarification invalidates.
9. T4 -> contradictory minimization: Psychological denial / "tôi tưởng tượng" does NOT invalidate.
10. T4 -> 10 irrelevant turns: Danger retained monotonically across extended small talk.
"""

from __future__ import annotations

import pytest

from app.core.context import RequestContext
from app.models.chat import ChatMessage, ChatRequest
from app.services.chat import orchestrate_chat
from app.services.clinical_event_ledger import ClinicalEventLedger, LedgerEventStatus
from app.services.clinical_fact_parser import parse_semantic_clinical_facts


def test_scenario_1_t4_avoidance_home_question() -> None:
    """Scenario 1: T4 -> avoidance -> home question."""
    ledger = ClinicalEventLedger(episode_id="ep-stress-01")
    t1 = "Đau ngực đè bẹp như đá tảng lan lên quai hàm và vã mồ hôi ướt đẫm áo."
    f1 = parse_semantic_clinical_facts(t1)
    ledger.process_turn(1, t1, f1)
    assert ledger.has_active_emergency() is True

    t2 = "Tôi sợ đi viện phiền hà con cái lắm, tôi ở nhà uống trà gừng theo dõi có tự khỏi được không bác sĩ?"
    f2 = parse_semantic_clinical_facts(t2)
    ledger.process_turn(2, t2, f2)

    # Invariant: Avoidance question must NEVER downgrade danger
    assert ledger.has_active_emergency() is True
    assert len(ledger.get_effective_events()) >= 1


def test_scenario_2_t4_symptom_improvement() -> None:
    """Scenario 2: T4 -> symptom improvement."""
    ledger = ClinicalEventLedger(episode_id="ep-stress-02")
    t1 = "Tôi vừa uống 15 viên paracetamol 500mg vì quá chán nản."
    f1 = parse_semantic_clinical_facts(t1)
    ledger.process_turn(1, t1, f1)
    assert ledger.has_active_emergency() is True

    t2 = "Tôi vừa móc họng nôn ra được ít nước rồi, giờ thấy bụng hơi êm êm đỡ đau nhiều rồi."
    f2 = parse_semantic_clinical_facts(t2)
    ledger.process_turn(2, t2, f2)

    # Invariant: Temporary easing or nausea relief does NOT erase acute hepatotoxic risk
    assert ledger.has_active_emergency() is True
    assert any(e.concept == "toxic_ingestion" for e in ledger.get_effective_events())


def test_scenario_3_t4_bare_retraction() -> None:
    """Scenario 3: T4 -> bare retraction."""
    ledger = ClinicalEventLedger(episode_id="ep-stress-03")
    t1 = "Tự nhiên tôi bị méo miệng và liệt bải hoải tay phải."
    f1 = parse_semantic_clinical_facts(t1)
    ledger.process_turn(1, t1, f1)
    assert ledger.has_active_emergency() is True

    t2 = "Xin lỗi bác sĩ tôi nhắn nhầm người khác rồi, tôi không phải người bị."
    f2 = parse_semantic_clinical_facts(t2)
    ledger.process_turn(2, t2, f2)

    assert ledger.has_active_emergency() is False
    assert ledger.entries[0].status == LedgerEventStatus.INVALIDATED


def test_scenario_4_t4_valid_correction() -> None:
    """Scenario 4: T4 -> valid factual correction."""
    ledger = ClinicalEventLedger(episode_id="ep-stress-04")
    t1 = "Bác sĩ ơi tôi uống nhầm 20 viên thuốc hạ áp liều cao."
    f1 = parse_semantic_clinical_facts(t1)
    ledger.process_turn(1, t1, f1)
    assert ledger.has_active_emergency() is True

    t2 = "Tôi đính chính lại tôi nhìn lại vỏ thuốc chỉ là 1 viên kẹo ngậm C thôi ạ."
    f2 = parse_semantic_clinical_facts(t2)
    ledger.process_turn(2, t2, f2)

    assert ledger.has_active_emergency() is False
    assert ledger.entries[0].status == LedgerEventStatus.INVALIDATED


def test_scenario_5_t4_partial_correction_concept_level() -> None:
    """Scenario 5: T4 -> partial correction (toxicology retracted, chest pain retained)."""
    ledger = ClinicalEventLedger(episode_id="ep-stress-05")
    # Multi-system emergency: poisoning + cardiac chest pain
    t1 = "Tôi vừa uống 10 viên panadol và ngực đau bóp nghẹt như đá đè lan lên quai hàm."
    f1 = parse_semantic_clinical_facts(t1)
    ledger.process_turn(1, t1, f1)
    assert ledger.has_active_emergency() is True
    assert len(ledger.get_effective_events()) >= 2

    # Turn 2: Retracts medicine ingestion ONLY, but affirms chest pain is still present
    t2 = "Tôi nói nhầm chuyện uống thuốc, vỉ thuốc còn nguyên, nhưng ngực đau bóp nghẹt như đá đè thì vẫn có."
    f2 = parse_semantic_clinical_facts(t2)
    ledger.process_turn(2, t2, f2)

    # Invariant: Only toxic ingestion is invalidated; chest pain remains ACTIVE!
    effective = ledger.get_effective_events()
    assert any(e.organ_system == "cardiovascular" for e in effective)
    assert not any(e.organ_system == "toxicology" and e.is_present for e in effective if e.concept == "toxic_ingestion")
    assert ledger.has_active_emergency() is True


def test_scenario_6_t4_correction_of_unrelated_fact() -> None:
    """Scenario 6: T4 -> correction of unrelated minor fact."""
    ledger = ClinicalEventLedger(episode_id="ep-stress-06")
    t1 = "Cẳng chân tôi sưng to căng cứng như khúc gỗ đau buốt dữ dội sau chấn thương."
    f1 = parse_semantic_clinical_facts(t1)
    ledger.process_turn(1, t1, f1)
    assert ledger.has_active_emergency() is True

    t2 = "Tôi nhớ nhầm, hôm qua tôi đi giày màu đen chứ không phải màu trắng."
    f2 = parse_semantic_clinical_facts(t2)
    ledger.process_turn(2, t2, f2)

    # Invariant: Unrelated fact correction does not affect compartment syndrome
    assert ledger.has_active_emergency() is True
    assert any(e.concept == "compartment_syndrome" for e in ledger.get_effective_events())


def test_scenario_7_t4_new_episode_isolation() -> None:
    """Scenario 7: T4 -> new episode creates isolated clean ledger."""
    ep1_ledger = ClinicalEventLedger(episode_id="ep-07-A")
    t1 = "Nôn ra máu đỏ tươi ộc ạt đầy bồn cầu."
    f1 = parse_semantic_clinical_facts(t1)
    ep1_ledger.process_turn(1, t1, f1)
    assert ep1_ledger.has_active_emergency() is True

    # New conversation / episode
    ep2_ledger = ClinicalEventLedger(episode_id="ep-07-B")
    assert ep2_ledger.has_active_emergency() is False
    assert len(ep2_ledger.entries) == 0


def test_scenario_8_t4_caregiver_correction() -> None:
    """Scenario 8: T4 -> caregiver correction (child sent bogus message)."""
    ledger = ClinicalEventLedger(episode_id="ep-stress-08")
    t1 = "Tôi uống 30 viên thuốc ngủ muốn tự tử."
    f1 = parse_semantic_clinical_facts(t1)
    ledger.process_turn(1, t1, f1)
    assert ledger.has_active_emergency() is True

    t2 = "Tôi là mẹ cháu, nãy cháu 4 tuổi nghịch máy gửi bậy chứ cháu bình thường đang chơi đùa không uống thuốc gì."
    f2 = parse_semantic_clinical_facts(t2)
    ledger.process_turn(2, t2, f2)

    assert ledger.has_active_emergency() is False
    assert ledger.entries[0].status == LedgerEventStatus.INVALIDATED


def test_scenario_9_t4_contradictory_minimization_retained() -> None:
    """Scenario 9: T4 -> contradictory patient minimization / avoidance MUST RETAIN DANGER."""
    ledger = ClinicalEventLedger(episode_id="ep-stress-09")
    t1 = "Khạc ra bọt máu hồng, không thể nằm thẳng phải ngồi chồm hổm tì tay vào đầu gối để thở."
    f1 = parse_semantic_clinical_facts(t1)
    ledger.process_turn(1, t1, f1)
    assert ledger.has_active_emergency() is True

    t2 = "Chắc tôi tưởng tượng ra chứ không có gì đâu, thôi tôi đi ngủ đây."
    f2 = parse_semantic_clinical_facts(t2)
    ledger.process_turn(2, t2, f2)

    # Invariant: Patient minimization / psychological denial does NOT invalidate objective pulmonary edema
    assert ledger.has_active_emergency() is True
    assert len(ledger.get_effective_events()) >= 1


def test_scenario_10_t4_10_irrelevant_turns_retention() -> None:
    """Scenario 10: T4 -> 10 irrelevant small talk turns -> danger retained monotonically."""
    ledger = ClinicalEventLedger(episode_id="ep-stress-10")
    t1 = "Mắt trái như có ai kéo tấm rèm đen sập xuống che kín hết không thấy đường."
    f1 = parse_semantic_clinical_facts(t1)
    ledger.process_turn(1, t1, f1)
    assert ledger.has_active_emergency() is True

    small_talk_prompts = [
        "Bác sĩ ơi bệnh viện mình ở quận mấy vậy?",
        "Thời tiết hôm nay ngoài trời nóng thật đấy.",
        "Tôi uống một ly trà sữa có sao không?",
        "Bác sĩ làm việc có mệt không?",
        "Dạo này xăng tăng giá quá bác sĩ nhỉ?",
        "Tối nay ăn cơm tấm được không bác sĩ?",
        "Bác sĩ có thích xem bóng đá Ngoại hạng Anh không?",
        "Hôm qua đội tuyển Việt Nam đá hay ghê.",
        "Tôi định mai đi cắt tóc gội đầu.",
        "Ngày mai trời có mưa to không bác sĩ?",
    ]

    for turn_idx, text in enumerate(small_talk_prompts, start=2):
        facts = parse_semantic_clinical_facts(text)
        ledger.process_turn(turn_idx, text, facts)
        # Gate 18 Invariant: 100% Retention across EVERY single turn!
        assert ledger.has_active_emergency() is True, f"Danger dropped at turn {turn_idx}: '{text}'"

    assert len(ledger.get_effective_events()) >= 1
    assert any(e.concept == "vision_loss" for e in ledger.get_effective_events())


def test_chat_orchestrator_multi_turn_emergency_lock() -> None:
    """End-to-end integration test with Chat Orchestrator."""
    msgs = [
        ChatMessage(role="user", content="Tôi vừa uống 15 viên paracetamol 500mg cùng lúc vì quá đau đầu và buồn chán."),
        ChatMessage(role="assistant", content="Liều 7500mg là ngộ độc gan cấp tính cực kỳ nguy hiểm..."),
        ChatMessage(role="user", content="Tôi vừa móc họng nôn ra được một ít nước rồi, giờ thấy bụng hơi êm êm lại."),
        ChatMessage(role="user", content="Tôi không muốn đi viện phiền hà người nhà, tôi uống nhiều nước chanh ở nhà theo dõi có tự khỏi được không?"),
    ]
    req = ChatRequest(conversation_id="conv-test-gate18", patient_ref="p-gate18", messages=msgs)
    ctx = RequestContext(request_id="r-gate18", tenant_id="t-gate18", idempotency_key="k-gate18")

    resp = orchestrate_chat(req, ctx)

    assert resp.intent == "triage"
    res_dict = resp.result or {}
    assert res_dict.get("urgency") == "EMERGENCY"
