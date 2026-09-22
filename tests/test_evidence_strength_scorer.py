"""Unit tests for Candidate V9 Workstream B: Evidence Strength Scorer."""

import pytest
from app.services.evidence_strength_scorer import (
    score_evidence_strength,
    SingletonEvidenceTier,
)


def test_critical_singleton_unilateral_blindness():
    text = "Đột nhiên không nhìn thấy một mắt, mắt trái nhìn tối thui."
    res = score_evidence_strength(text)
    assert res.tier == SingletonEvidenceTier.CRITICAL_SINGLETON
    assert res.recommended_floor == "EMERGENCY"
    assert res.requires_targeted_clarification is False


def test_critical_singleton_focal_weakness():
    text = "Tự nhiên tay cầm cốc nước thấy yếu đột ngột không giữ được."
    res = score_evidence_strength(text)
    assert res.tier == SingletonEvidenceTier.CRITICAL_SINGLETON
    assert res.recommended_floor == "EMERGENCY"


def test_critical_singleton_infant_bulging_fontanelle():
    text = "Bé 5 tháng tuổi sốt và thấy thóp phồng căng lên."
    res = score_evidence_strength(text)
    assert res.tier == SingletonEvidenceTier.CRITICAL_SINGLETON
    assert res.recommended_floor == "EMERGENCY"


def test_strong_singleton_with_and_without_context():
    text = "Đau đầu sét đánh dữ dội chưa từng có."
    res_isolated = score_evidence_strength(text, has_supporting_context=False)
    assert res_isolated.tier == SingletonEvidenceTier.STRONG_SINGLETON
    assert res_isolated.recommended_floor == "URGENT"

    res_supported = score_evidence_strength(text, has_supporting_context=True)
    assert res_supported.tier == SingletonEvidenceTier.STRONG_SINGLETON
    assert res_supported.recommended_floor == "EMERGENCY"


def test_weak_singleton_no_false_escalation():
    text = "Tôi thấy mệt mỏi sau khi làm việc ca đêm về."
    res = score_evidence_strength(text)
    assert res.tier == SingletonEvidenceTier.WEAK_SINGLETON
    assert res.recommended_floor == "ROUTINE"


def test_ambiguous_singleton_micturition():
    text = "Tôi bị ngất khi đi tiểu đêm qua."
    res = score_evidence_strength(text)
    assert res.tier == SingletonEvidenceTier.AMBIGUOUS_SINGLETON
    assert res.recommended_floor == "ROUTINE"
    assert res.requires_targeted_clarification is True
