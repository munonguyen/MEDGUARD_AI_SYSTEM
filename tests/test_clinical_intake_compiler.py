"""Unit Tests for Clinical Intake Compiler & Dual Representation."""

import pytest
from app.services.clinical_intake_compiler import ClinicalIntakeCompiler


def test_compile_complex_messy_user_query_1():
    """Test Case 1: The messy patient query described in the design document."""
    query = (
        "bác ơi mấy hôm nay kiểu em cũng không biết là do tập gym hay gì nhưng chân bên trái "
        "đoạn dưới đầu gối nó cứ căng căng sáng ngủ dậy thấy hơn nhưng đi lại thì vẫn được "
        "hôm kia có chạy bộ cũng hơi nhiều mà em thấy trên mạng nói cục máu đông nên hơi sợ "
        "không biết có nguy hiểm ko với em đang uống thuốc dị ứng nữa"
    )

    compiled = ClinicalIntakeCompiler.compile(query)

    # 1. Check raw preservation
    assert compiled.raw_query == query
    assert "bác sĩ ơi" in compiled.normalized_query or "bác ơi" in compiled.normalized_query
    assert "nguy hiểm không" in compiled.normalized_query

    # 2. Check Complexity Classification
    assert compiled.complexity_level == "C2"

    # 3. Check Dual Representation: Semantic Form
    assert compiled.semantic_form.primary_intent == "risk_assessment"
    assert compiled.semantic_form.emotional_tone == "anxious"
    assert len(compiled.semantic_form.patient_concerns) >= 1
    
    # CRITICAL INVARIANT: Blood clot is a patient hypothesis / fear, NOT a confirmed diagnosis!
    fear = compiled.semantic_form.patient_concerns[0]
    assert "Huyết khối" in fear.stated_concern or "cục máu đông" in fear.stated_concern.lower()
    assert fear.is_clinical_diagnosis is False
    assert fear.source == "internet_search"

    # 4. Check Dual Representation: Clinical Form
    assert "calf_tightness_mild_moderate" in compiled.clinical_form.positive_findings
    assert compiled.clinical_form.functional_status == "ambulatory_preserved"
    assert any("left_calf" in site for site in compiled.clinical_form.anatomical_sites)

    # 5. Check Timeline Extraction
    timeline_offsets = [t.time_offset for t in compiled.clinical_form.timeline]
    assert "-2d" in timeline_offsets  # hôm kia chạy bộ
    assert "today_morning" in timeline_offsets  # sáng ngủ dậy

    # 6. Check Medication Extraction
    assert len(compiled.clinical_form.medications) >= 1
    med = compiled.clinical_form.medications[0]
    assert med.therapeutic_class == "antihistamine_h1"

    # 7. Check Question Decomposition
    assert len(compiled.decomposed_questions) >= 3
    q_domains = [q.focus_domain for q in compiled.decomposed_questions]
    assert "symptom_risk" in q_domains
    assert "drug_interaction" in q_domains
    assert "red_flags" in q_domains


def test_compile_complex_messy_user_query_2_with_teencode_and_age():
    """Test Case 2: Teencode, age extraction, exact drug brand, negations."""
    query = (
        "em cũng ko rõ nữa mấy hôm trước em chạy rồi về chân hơi căng mà em tưởng bình thường "
        "sáng nay thấy vẫn vậy nhưng ko đỏ hay j cả đi vẫn được em 24t ko bệnh j có điều đang "
        "uống thuốc dị ứng cetri gì đó đọc mạng bảo huyết khối nên em sợ liệu có phải đi viện ko hay chườm được"
    )

    compiled = ClinicalIntakeCompiler.compile(query)

    # 1. Teencode normalization
    assert "không đỏ hay gì cả" in compiled.normalized_query
    assert "24 tuổi" in compiled.normalized_query
    assert "đi viện không" in compiled.normalized_query

    # 2. Age extraction
    assert compiled.clinical_form.patient_age == 24

    # 3. Negation extraction
    neg_concepts = [n.concept for n in compiled.clinical_form.negative_findings]
    assert "calf_redness_absent" in neg_concepts
    assert "walking_preserved" in neg_concepts
    assert "no_underlying_disease" in neg_concepts

    # 4. Medication resolution
    meds = compiled.clinical_form.medications
    assert len(meds) >= 1
    assert meds[0].candidate_active_ingredient == "cetirizine"
    assert meds[0].therapeutic_class == "antihistamine_h1"
    assert meds[0].certainty == "PROBABLE"

    # 5. Fear separation
    assert len(compiled.semantic_form.patient_concerns) >= 1
    assert compiled.semantic_form.patient_concerns[0].is_clinical_diagnosis is False
    assert compiled.semantic_form.patient_concerns[0].source == "internet_search"

    # 6. High-value missing fields
    assert any("swelling" in f for f in compiled.high_value_missing_fields)
