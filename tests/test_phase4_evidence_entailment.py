"""Unit Tests for Phase 4D: Evidence Entailment Engine (Claim-Evidence NLI)."""

import pytest
from app.services.evidence_entailment import EvidenceEntailmentEngine


def test_entailment_detects_overclaiming_and_certainty_escalation():
    # Source provides differential caution, but claim asserts 100% certainty
    evidence_stmt = "Sưng đau một bên bắp chân cần được đánh giá nghi ngờ huyết khối tĩnh mạch sâu (DVT)."
    claim_text = "Bạn chắc chắn 100% đang bị huyết khối tĩnh mạch sâu (DVT)."

    res = EvidenceEntailmentEngine.evaluate(
        claim_id="C_OVERCLAIM_1",
        claim_text=claim_text,
        evidence_id="EV_DVT_001",
        evidence_statement=evidence_stmt,
    )

    assert res.relation == "PARTIALLY_SUPPORTS"
    assert res.over_claiming_detected is True
    assert "Hạ cấp khẳng định chắc chắn" in (res.mitigation_recommendation or "")


def test_entailment_detects_negation_mismatch():
    # Source strictly prohibits Aspirin in Dengue, claim suggests it
    evidence_stmt = "Tuyệt đối chống chỉ định dùng Aspirin trong điều trị sốt nghi do sốt xuất huyết Dengue."
    claim_text = "Bạn có thể dùng Aspirin để hạ sốt và giảm đau."

    res = EvidenceEntailmentEngine.evaluate(
        claim_id="C_NEG_1",
        claim_text=claim_text,
        evidence_id="EV_ASPIRIN_001",
        evidence_statement=evidence_stmt,
    )

    assert res.relation == "CONTRADICTS"
    assert res.negation_mismatch is True
    assert res.confidence >= 0.95


def test_entailment_approves_faithful_supported_claim():
    evidence_stmt = "Căng mỏi cơ sau vận động có thể tự chăm sóc tại nhà bằng nghỉ ngơi và chườm lạnh tại chỗ."
    claim_text = "Nghỉ ngơi và chườm lạnh tại chỗ giúp giảm căng mỏi cơ sau khi vận động."

    res = EvidenceEntailmentEngine.evaluate(
        claim_id="C_SUPPORT_1",
        claim_text=claim_text,
        evidence_id="EV_STRAIN_001",
        evidence_statement=evidence_stmt,
    )

    assert res.relation == "SUPPORTS"
    assert res.over_claiming_detected is False
    assert res.confidence >= 0.85


def test_entailment_flags_irrelevant_citation():
    evidence_stmt = "Điều trị viêm loét dạ dày bằng thuốc ức chế bơm proton PPI."
    claim_text = "Bệnh nhân có triệu chứng đau mắt đỏ và viêm kết mạc dị ứng."

    res = EvidenceEntailmentEngine.evaluate(
        claim_id="C_IRREL_1",
        claim_text=claim_text,
        evidence_id="EV_PPI_001",
        evidence_statement=evidence_stmt,
    )

    assert res.relation == "NOT_RELEVANT"
