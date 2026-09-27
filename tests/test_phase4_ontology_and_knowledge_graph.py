"""Unit Tests for Phase 4C: Medical Knowledge Graph & Clinical Ontology."""

import pytest
from app.knowledge.graph.ontology import ClinicalOntology


def test_ontology_resolves_vietnamese_lay_terms_and_teencode():
    ont = ClinicalOntology.create_default()

    # Brand names and slang for Paracetamol
    assert ont.resolve_concept("para") == "drug.paracetamol"
    assert ont.resolve_concept("thuốc hạ sốt") == "drug.paracetamol"
    assert ont.resolve_concept("panadol") == "drug.paracetamol"
    assert ont.resolve_concept("efferalgan") == "drug.paracetamol"

    # Anticoagulants vs Specific Active Ingredients
    assert ont.resolve_concept("thuốc chống đông") == "drug_class.anticoagulant"
    assert ont.resolve_concept("sintrom") == "drug.acenocoumarol"
    assert ont.resolve_concept("warfarin") == "drug.warfarin"

    # Detail resolution with clarification requirement for classes
    detail_class = ont.resolve_concept_details("thuốc chống đông")
    assert detail_class.is_class is True
    assert detail_class.clarification_required is True

    detail_specific = ont.resolve_concept_details("sintrom")
    assert detail_specific.is_class is False
    assert detail_specific.specific_drug_id == "drug.acenocoumarol"
    assert detail_specific.clarification_required is False

    # Deep vein thrombosis
    assert ont.resolve_concept("cục máu đông tĩnh mạch") == "disease.dvt"
    assert ont.resolve_concept("dvt") == "disease.dvt"


def test_ontology_extracts_all_matched_concepts_from_noisy_text():
    ont = ClinicalOntology.create_default()

    utterance = "Em uống thuốc hạ sốt panadol với thuốc chống đông warfarin mà nay đau bắp chân"
    matched = ont.resolve_all_concepts(utterance)

    assert "drug.paracetamol" in matched
    assert "drug.warfarin" in matched
    assert "symptom.calf_pain" in matched


def test_knowledge_graph_queries_drug_drug_interaction():
    ont = ClinicalOntology.create_default()

    interactions = ont.query_interactions("Warfarin", "Ibuprofen")
    assert len(interactions) >= 1
    rel = interactions[0]
    assert rel.predicate == "interacts_with"
    assert rel.severity == "major"
    assert "xuất huyết" in rel.mechanism
    assert rel.source_id == "BYT_DUOC_THU_2022"


def test_knowledge_graph_queries_drug_disease_contraindication():
    ont = ClinicalOntology.create_default()

    # Aspirin in Dengue
    contra = ont.query_contraindications("Aspirin", "Sốt xuất huyết Dengue")
    assert len(contra) >= 1
    assert contra[0].predicate == "contraindicated_in"
    assert contra[0].severity == "critical"
    assert "tiểu cầu" in contra[0].mechanism

    # Aspirin in Peptic Ulcer
    ulcer_contra = ont.query_contraindications("Aspirin", "Loét dạ dày tá tràng")
    assert len(ulcer_contra) >= 1
    assert ulcer_contra[0].severity == "major"


def test_knowledge_graph_traverses_disease_red_flags_and_differentials():
    ont = ClinicalOntology.create_default()

    # DVT red flag: Unilateral swelling
    rf_rels = ont.query_relations(subject_id="disease.dvt", predicate="has_red_flag")
    assert len(rf_rels) >= 1
    assert rf_rels[0].object_id == "red_flag.unilateral_leg_edema"

    # DVT differential: Muscle strain
    diff_rels = ont.query_relations(subject_id="disease.dvt", predicate="differential_of")
    assert len(diff_rels) >= 1
    assert diff_rels[0].object_id == "disease.muscle_strain"
