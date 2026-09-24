"""Unit tests for Candidate V9 Workstream C: Toxicity Signature Router & Reasoner."""

import pytest
from app.services.toxicology_signature_router import (
    route_by_toxicity_signature,
    ToxicityDimension,
)
from app.services.toxicology_reasoner import (
    evaluate_toxicology,
    ToxicologyUrgency,
)


def test_herbal_wine_alkaloid_toxicity_signature():
    text = "Vừa uống rượu ngâm củ ấu tàu gia truyền xong thấy tim đập chậm nguy hiểm, tê rần môi miệng và hoa mắt."
    sig = route_by_toxicity_signature(text)
    assert sig.is_toxicology_eligible is True
    assert sig.is_emergency_toxidrome is True
    assert ToxicityDimension.EXPOSURE_EVENT in sig.matched_dimensions
    assert ToxicityDimension.CARDIOVASCULAR_SIGNS in sig.matched_dimensions

    tox_res = evaluate_toxicology(text)
    assert tox_res.urgency == ToxicologyUrgency.EMERGENCY
    assert tox_res.is_life_threatening is True


def test_wild_mushroom_gi_toxicity_signature():
    text = "Sau khi ăn nấm lạ trong rừng 1 tiếng, giờ nôn mửa liên tục và tiêu chảy xối xả, đau bụng quằn quại."
    sig = route_by_toxicity_signature(text)
    assert sig.is_toxicology_eligible is True
    assert sig.is_emergency_toxidrome is True
    assert ToxicityDimension.GI_DISTURBANCE in sig.matched_dimensions

    tox_res = evaluate_toxicology(text)
    assert tox_res.urgency == ToxicologyUrgency.EMERGENCY


def test_corrosive_cleaning_chemical_signature():
    text = "Uống nhầm nước tẩy rửa javen, thấy bỏng rát thực quản dữ dội và nôn liên tục."
    sig = route_by_toxicity_signature(text)
    assert sig.is_toxicology_eligible is True
    assert sig.is_emergency_toxidrome is True

    tox_res = evaluate_toxicology(text)
    assert tox_res.urgency == ToxicologyUrgency.EMERGENCY


def test_pediatric_unknown_pill_ingestion():
    text = "Bé 3 tuổi chơi cạnh lọ thuốc mở nắp, nuốt nhiều viên thuốc, giờ đang nôn trớ không ngừng và lơ mơ."
    sig = route_by_toxicity_signature(text)
    assert sig.is_toxicology_eligible is True
    assert sig.is_emergency_toxidrome is True

    tox_res = evaluate_toxicology(text)
    assert tox_res.urgency == ToxicologyUrgency.EMERGENCY


def test_benign_food_intake_no_false_toxic_routing():
    text = "Tôi ăn bát bún bò buổi sáng hơi cay một chút, bụng hơi cồn cào nhẹ."
    sig = route_by_toxicity_signature(text)
    assert sig.is_toxicology_eligible is False
    assert sig.is_emergency_toxidrome is False

    tox_res = evaluate_toxicology(text)
    assert tox_res.urgency == ToxicologyUrgency.ROUTINE
