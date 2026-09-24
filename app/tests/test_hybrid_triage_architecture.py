"""Unit tests for the Hybrid Conservative Triage Architecture.

Verifies the 4 critical safety invariants:
  1. Unknown symptom rules NEVER fall back to ROUTINE (must return UNRESOLVED).
  2. Multi-turn emergency escalation overrides prior routine status.
  3. Patient symptom improvement or relief does NOT erase prior emergency risk.
  4. Semantic risk evaluator exceptions FAIL CLOSED to URGENT (never ROUTINE).
  5. Dialect mapping preserves original tokens while enriching medical concepts.
"""

from __future__ import annotations

import pytest

from app.core.context import RequestContext
from app.models.triage import TriageRequest
from app.services.clinical_text import normalize_clinical_concepts
from app.services.risk_memory import RiskState, merge_risk, should_start_new_episode
from app.services.rules import triage_rules
from app.services.semantic_risk import (
    SemanticRiskEvaluator,
    safe_semantic_evaluate,
)
from app.services.triage import evaluate_triage
from app.services.triage_resolver import highest_urgency, resolve_triage


def test_unknown_rule_does_not_fallback_to_routine():
    """Invariant 1: An unmapped/unknown symptom statement must NOT silently default to ROUTINE."""
    result = triage_rules(
        symptoms_text="một biểu hiện lâm sàng kỳ lạ chưa từng có trong từ điển quy tắc",
        vitals=None,
    )
    assert result.urgency == "UNRESOLVED"
    assert result.matched is False
    assert result.confidence == 0.0


def test_later_emergency_overrides_previous_routine():
    """Invariant 2: When turn 2 reports emergency signs, cumulative risk escalates to EMERGENCY."""
    previous = RiskState(highest_urgency="ROUTINE")
    state = merge_risk(
        previous,
        current_urgency="EMERGENCY",
        current_red_flags=["new_focal_neurologic_deficit"],
    )
    assert state.highest_urgency == "EMERGENCY"
    assert "new_focal_neurologic_deficit" in state.red_flags


def test_improvement_does_not_erase_prior_emergency():
    """Invariant 3a: Temporary symptom relief in turn 2 does NOT downgrade prior emergency."""
    previous = RiskState(
        highest_urgency="EMERGENCY",
        red_flags=["thunderclap_headache"],
    )
    state = merge_risk(
        previous,
        current_urgency="ROUTINE",
        current_red_flags=[],
    )
    assert state.highest_urgency == "EMERGENCY"
    assert "thunderclap_headache" in state.red_flags


def test_explicit_correction_invalidates_prior_danger_and_recomputes():
    """Invariant 3b: Explicit user fact correction invalidates prior erroneous danger and recomputes."""
    from app.services.risk_memory import is_explicit_correction

    correction_text = "Xin lỗi tôi nhập nhầm bệnh của người khác. Tôi chỉ đau cơ vai sau tập."
    assert is_explicit_correction(correction_text) is True

    previous = RiskState(
        highest_urgency="EMERGENCY",
        red_flags=["respiratory_failure_cyanosis"],
    )
    state = merge_risk(
        previous,
        current_urgency="ROUTINE",
        current_red_flags=[],
        current_reasons=["muscle_soreness_after_workout"],
        is_correction=True,
    )
    assert state.highest_urgency == "ROUTINE"
    assert state.correction_applied is True
    assert "respiratory_failure_cyanosis" not in state.red_flags
    assert "muscle_soreness_after_workout" in state.reasons


def test_semantic_failure_never_returns_routine():
    """Invariant 4: If semantic evaluation fails, it must fail-closed to URGENT, never ROUTINE."""
    class BrokenEvaluator(SemanticRiskEvaluator):
        def evaluate(self, text, **kwargs):
            raise RuntimeError("LLM service unavailable")

    evaluator = BrokenEvaluator()
    result = safe_semantic_evaluate(
        evaluator,
        "tôi bị triệu chứng khó chịu",
    )
    assert result.urgency in ("URGENT", "EMERGENCY")
    assert result.urgency != "ROUTINE"
    assert result.uncertain is True


def test_dialect_normalization_enriches_concepts():
    """Invariant 5: Dialect mapping enriches medical concepts without erasing source terms."""
    text = "Ông nhà tôi bị trúng gió độc cấm khẩu méo xệch một bên miệng"
    normalized = normalize_clinical_concepts(text)
    assert "cam khau" in normalized
    assert "khong noi duoc" in normalized
    assert "meo xech" in normalized
    assert "mat can doi" in normalized


def test_conservative_resolver_escalation():
    """Test conservative max resolution across rule, semantic, and conversation signals."""
    res = resolve_triage(
        rule_urgency="ROUTINE",
        semantic_urgency="EMERGENCY",
        historical_urgency=None,
    )
    assert res.urgency == "EMERGENCY"

    res2 = resolve_triage(
        rule_urgency="UNRESOLVED",
        semantic_urgency="URGENT",
        historical_urgency=None,
    )
    assert res2.urgency == "URGENT"

    res3 = resolve_triage(
        rule_urgency=None,
        semantic_urgency=None,
        historical_urgency=None,
    )
    assert res3.urgency == "URGENT"  # Fail safe when no signal


def test_adversarial_retraction_without_replacement_fact():
    """Test adversarial defense against bare retractions and patient avoidance."""
    from app.services.risk_memory import is_explicit_correction

    # Bare retractions without replacement facts must be REJECTED
    assert is_explicit_correction("À tôi nói nhầm.") is False
    assert is_explicit_correction("nói nhầm thôi") is False
    assert is_explicit_correction("tôi nói lộn") is False

    # Avoidance language seeking to dismiss emergency must be REJECTED
    assert is_explicit_correction("Thực ra vẫn đau ngực nhưng chỉ muốn bạn đừng bảo tôi đi viện.") is False
    assert is_explicit_correction("Nhầm rồi đừng bảo tôi đi viện tôi sợ đi viện lắm.") is False

    # Genuine substantiated corrections WITH replacement facts must be ACCEPTED
    assert is_explicit_correction("Xin lỗi tôi gõ nhầm, thực ra chỉ bị mỏi cơ vai sau buổi nâng tạ hôm qua.") is True
    assert is_explicit_correction("Tôi nhìn lại vỏ thuốc thì thấy chỉ uống 1 viên thôi chứ không phải 10 viên.") is True
    assert is_explicit_correction("Đo lại nhiệt độ là 36.8 độ bình thường, tôi nhìn nhầm nhiệt kế.") is True


def test_benign_unrecognized_inquiries_remain_routine():
    """Verify that low-risk lifestyle and transient resolved complaints do NOT get escalated to URGENT."""
    ctx = RequestContext(request_id="test-benign", tenant_id="test", idempotency_key="test-key")
    queries = [
        "Da ngón út tôi hơi khô hai hôm nay.",
        "Tôi muốn hỏi uống nước trước hay sau ăn.",
        "Tôi bị nấc 3 phút rồi hết.",
    ]
    for q in queries:
        req = TriageRequest(patient_ref="p", symptoms_text=q)
        resp = evaluate_triage(req, ctx=ctx)
        assert resp.urgency == "ROUTINE", f"Query '{q}' was unexpectedly escalated to {resp.urgency}"


def test_subtle_symptom_improvement_disguised_as_correction():
    """Test that cessation of symptoms ('không đau nữa') disguised as 'nói nhầm' is NOT accepted as correction."""
    from app.services.risk_memory import is_explicit_correction, is_symptom_improvement

    # 1. 'I never had chest pain; that was another person's symptom' -> VALID CORRECTION
    valid_correction = "Tôi nói nhầm, tôi chưa từng bị đau ngực; đó là tôi hỏi hộ người nhà."
    assert is_explicit_correction(valid_correction) is True

    # 2. 'Actually my chest pain is gone now' disguised with 'nói nhầm' -> SYMPTOM IMPROVEMENT, NOT CORRECTION!
    disguised_improvement = "Tôi nói nhầm chuyện đau ngực. Thực ra tôi không đau ngực nữa."
    assert is_explicit_correction(disguised_improvement) is False
    assert is_symptom_improvement(disguised_improvement) is True

    # 3. 'I don't want to have chest pain anymore' -> NEITHER (AVOIDANCE/WISHFUL THINKING)
    wishful_thinking = "Tôi không muốn bị đau ngực nữa, đừng bảo tôi đi viện."
    assert is_explicit_correction(wishful_thinking) is False


def test_medication_dose_reasoning_toxicology_and_treatment_separation():
    """Test pharmacokinetic dose reasoning and strict separation of triage from treatment directives."""
    from app.services.dose_reasoning import extract_paracetamol_dose_assessment

    # Case A: Acute 10 tablets 500mg = 5000mg -> EMERGENCY
    res10 = extract_paracetamol_dose_assessment("Tôi uống 10 viên Paracetamol 500mg một lúc từ lúc nãy!")
    assert res10 is not None
    assert res10.urgency == "EMERGENCY"
    assert res10.risk_level == "HIGH"
    assert res10.total_dose_mg == 5000.0

    # Case B: Acute 9 tablets 500mg = 4500mg -> EMERGENCY (not missed by hard-coded '10 viên')
    res9 = extract_paracetamol_dose_assessment("Tôi lỡ uống 9 viên Panadol 500mg cùng một lúc.")
    assert res9 is not None
    assert res9.urgency == "EMERGENCY"
    assert res9.risk_level == "HIGH"
    assert res9.total_dose_mg == 4500.0

    # Case C: Child 30kg taking 9 tablets 500mg -> 150 mg/kg -> EMERGENCY
    res_child = extract_paracetamol_dose_assessment("Bé 30kg uống 9 viên paracetamol 500mg một lần.")
    assert res_child is not None
    assert res_child.urgency == "EMERGENCY"
    assert res_child.dose_mg_per_kg == 150.0

    # Case D: Heavy patient 110kg taking 10 tablets 325mg = 3250mg -> URGENT (supratherapeutic, but < 4g and < 30mg/kg)
    res_heavy = extract_paracetamol_dose_assessment("Người lớn nặng 110kg uống 10 viên paracetamol 325mg.")
    assert res_heavy is not None
    assert res_heavy.urgency == "URGENT"
    assert res_heavy.risk_level == "MODERATE"
    assert res_heavy.dose_mg_per_kg < 30.0

    # Case E: Staggered 5g in 24 hours vs single acute 5g
    res_staggered = extract_paracetamol_dose_assessment("Tôi uống 5g paracetamol chia làm 5 lần rải rác trong 24 giờ.")
    assert res_staggered is not None
    assert res_staggered.urgency == "URGENT"
    assert res_staggered.ingestion_pattern == "staggered"

    # Case F: Triage vs Treatment separation check
    # Recommendation must NOT prescribe invasive procedures like gastric lavage or mandate NAC
    recommendation = res10.triage_recommendation
    assert "rửa dạ dày" not in recommendation.lower()
    assert "bắt buộc" not in recommendation.lower()
    assert "cấp cứu 115" in recommendation.lower() or "khoa cấp cứu" in recommendation.lower()
    assert "bao bì" in recommendation.lower() or "vỏ thuốc" in recommendation.lower()
    assert "không tự gây nôn" in recommendation.lower()

