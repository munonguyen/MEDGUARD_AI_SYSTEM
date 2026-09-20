"""Unit tests for Physiologic Consequence Layer (V7 Architecture).

Verifies that acute pathophysiologic breakdown patterns are accurately deduced
from clinical facts independently of disease names, while strictly adhering to
negation, temporality, and benign control invariants.
"""

from __future__ import annotations

import pytest

from app.models.clinical_events import ClinicalFactSet
from app.models.physiologic_consequences import (
    ConsequenceSeverity,
    PhysiologicAssessment,
    PhysiologicConsequenceType,
)
from app.services.clinical_fact_parser import parse_semantic_clinical_facts
from app.services.clinical_threat_graph import evaluate_threat_graph, ThreatLevel
from app.services.physiologic_consequence_engine import deduce_physiologic_consequences


def test_major_barrier_failure_necrotizing():
    text = "Vết xước mu bàn chân sưng đỏ tím lan nhanh, ấn lép bép có bóng nước đen rỉ dịch hôi thối, đau buốt dữ dội."
    facts = parse_semantic_clinical_facts(text)
    assessment = deduce_physiologic_consequences(facts)

    assert assessment.has_emergency_consequence
    consequence_types = [c.consequence_type for c in assessment.emergency_consequences]
    assert PhysiologicConsequenceType.MAJOR_BARRIER_FAILURE in consequence_types

    threat = evaluate_threat_graph(facts)
    assert threat.max_threat_level == ThreatLevel.CRITICAL
    assert "limb_threat" in threat.critical_dimensions


def test_circulatory_compromise_and_septic_shock():
    text = "Bệnh nhân sốt rét run huyết áp tụt 75/45 thở hổn hển 30 lần/phút da tái xanh nổi vân tím."
    facts = parse_semantic_clinical_facts(text)
    assessment = deduce_physiologic_consequences(facts)

    assert assessment.has_emergency_consequence
    consequence_types = [c.consequence_type for c in assessment.emergency_consequences]
    assert PhysiologicConsequenceType.CIRCULATORY_COMPROMISE in consequence_types
    assert PhysiologicConsequenceType.RESPIRATORY_FAILURE in consequence_types

    threat = evaluate_threat_graph(facts)
    assert threat.max_threat_level == ThreatLevel.CRITICAL
    assert "circulation" in threat.critical_dimensions or "breathing" in threat.critical_dimensions


def test_wound_evisceration_and_perforation():
    text = "Vết mổ sau phẫu thuật bỗng bục chỉ rỉ máu mủ ồ ạt ruột non lồi qua vết mổ đau đớn dữ dội."
    facts = parse_semantic_clinical_facts(text)
    assessment = deduce_physiologic_consequences(facts)

    assert assessment.has_emergency_consequence
    consequence_types = [c.consequence_type for c in assessment.emergency_consequences]
    assert PhysiologicConsequenceType.PERFORATION_RISK in consequence_types

    threat = evaluate_threat_graph(facts)
    assert threat.max_threat_level == ThreatLevel.CRITICAL
    assert "surgical_abdomen" in threat.critical_dimensions


def test_geriatric_fracture_with_shock():
    text = "Cụ ông 88 tuổi trượt chân ngã đau chói khớp háng không đứng dậy được, chân ngắn xoay ngoài mạch nhanh huyết áp 85/50."
    facts = parse_semantic_clinical_facts(text)
    assessment = deduce_physiologic_consequences(facts)

    assert assessment.has_emergency_consequence
    consequence_types = [c.consequence_type for c in assessment.emergency_consequences]
    assert PhysiologicConsequenceType.INTERNAL_HEMORRHAGE in consequence_types or PhysiologicConsequenceType.CIRCULATORY_COMPROMISE in consequence_types

    threat = evaluate_threat_graph(facts)
    assert threat.max_threat_level == ThreatLevel.CRITICAL
    assert "circulation" in threat.critical_dimensions


def test_neuroleptic_malignant_syndrome():
    text = "Sốt cao cứng cơ toàn thân vã mồ hôi sau khi tăng liều thuốc an thần Haloperidol."
    facts = parse_semantic_clinical_facts(text)
    assessment = deduce_physiologic_consequences(facts)

    assert assessment.has_emergency_consequence
    consequence_types = [c.consequence_type for c in assessment.emergency_consequences]
    assert PhysiologicConsequenceType.SYSTEMIC_TOXIC_STATE in consequence_types

    threat = evaluate_threat_graph(facts)
    assert threat.max_threat_level == ThreatLevel.CRITICAL
    assert "toxic_exposure" in threat.critical_dimensions


def test_septic_arthritis():
    text = "Khớp gối sưng to nóng đỏ dữ dội sau tiêm khớp 3 ngày, sốt cao 39.8 độ rét run không thể đặt chân xuống đất."
    facts = parse_semantic_clinical_facts(text)
    assessment = deduce_physiologic_consequences(facts)

    assert assessment.has_emergency_consequence
    consequence_types = [c.consequence_type for c in assessment.emergency_consequences]
    assert PhysiologicConsequenceType.TIME_CRITICAL_ORGAN_LOSS in consequence_types

    threat = evaluate_threat_graph(facts)
    assert threat.max_threat_level == ThreatLevel.CRITICAL


def test_negation_invariants():
    text = "Tôi đọc trên mạng thấy người ta nói vết thương hoại tử ấn lép bép có bóng nước đen, nhưng tôi không bị như vậy."
    facts = parse_semantic_clinical_facts(text)
    assessment = deduce_physiologic_consequences(facts)

    assert not assessment.has_emergency_consequence
    threat = evaluate_threat_graph(facts)
    assert threat.max_threat_level != ThreatLevel.CRITICAL


def test_benign_control_brain_freeze():
    text = "Cắn một miếng kem đá bào to bỗng đau buốt dữ dội thấu óc trong 15 giây, sau đó hết sạch cơn đau đầu, hiện khỏe mạnh bình thường."
    facts = parse_semantic_clinical_facts(text)
    assessment = deduce_physiologic_consequences(facts)

    assert not assessment.has_emergency_consequence
