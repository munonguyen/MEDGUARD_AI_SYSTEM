"""Unit tests for Candidate V9 Workstream A: Semantic Relation Extractor & Abstraction Lattice."""

import pytest
from app.services.semantic_relation_extractor import extract_semantic_relations
from app.services.semantic_abstraction_lattice import (
    evaluate_abstraction_lattice,
    AbstractThreatArchetype,
)


def test_loss_of_perfusion_vascular_threat():
    text = "Chân lạnh buốt, da trắng bệch, sờ mạch không thấy đập từ 20 phút nay."
    graph = extract_semantic_relations(text)
    assert graph.has_concept("cold_extremity")
    assert graph.has_concept("pallor_or_cyanosis")
    assert graph.has_concept("absent_or_weak_pulse")

    result = evaluate_abstraction_lattice(graph)
    assert result.has_emergency_threat is True
    assert result.dominant_threat.archetype == AbstractThreatArchetype.LOSS_OF_PERFUSION


def test_context_differentiation_benign_musculoskeletal_chest():
    text = "Tôi mới hít đất tập gym xong thấy ngực bị đè nặng, ấn vào thì thấy đau nhói tại thành ngực, không vã mồ hôi."
    graph = extract_semantic_relations(text)
    assert graph.has_concept("reproducible_chest_wall_pain")
    assert not graph.has_concept("diaphoresis")

    result = evaluate_abstraction_lattice(graph)
    assert result.has_emergency_threat is False
    assert result.has_benign_override is True
    assert result.dominant_threat.archetype == AbstractThreatArchetype.BENIGN_MUSCULOSKELETAL_CHEST


def test_ischemic_cardiopulmonary_threat():
    text = "Bị tức ngực dữ dội như đá đè khi leo cầu thang, kèm vã mồ hôi lạnh và lan lên vai trái."
    graph = extract_semantic_relations(text)
    assert graph.has_concept("chest_pressure")
    assert graph.has_concept("diaphoresis")
    assert graph.has_concept("radiation_to_arm_or_jaw")

    result = evaluate_abstraction_lattice(graph)
    assert result.has_emergency_threat is True
    assert result.dominant_threat.archetype == AbstractThreatArchetype.CARDIOPULMONARY_THREAT


def test_cerebrovascular_stroke_focal_deficit():
    text = "Một bên khóe miệng thấy tê rần và nước bọt hơi chảy, tay cầm cốc nước thấy yếu đột ngột."
    graph = extract_semantic_relations(text)
    assert graph.has_concept("facial_droop_or_numbness")
    assert graph.has_concept("focal_weakness")

    result = evaluate_abstraction_lattice(graph)
    assert result.has_emergency_threat is True
    assert result.dominant_threat.archetype == AbstractThreatArchetype.CEREBROVASCULAR_CATASTROPHE


def test_benign_micturition_syncope():
    text = "Nửa đêm dậy đi tiểu xong tự nhiên bị ngất xỉu rồi tỉnh lại ngay, không đau ngực không khó thở."
    graph = extract_semantic_relations(text)
    assert graph.has_concept("micturition_syncope")

    result = evaluate_abstraction_lattice(graph)
    assert result.has_emergency_threat is False
    assert result.has_benign_override is True
    assert result.dominant_threat.archetype == AbstractThreatArchetype.BENIGN_VASOVAGAL_SYNCOPE
