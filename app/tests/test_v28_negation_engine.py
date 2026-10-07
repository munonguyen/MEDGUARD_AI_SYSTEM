import pytest
from app.services.clinical_reasoning.negation_engine import NegationEngine


@pytest.fixture
def engine():
    return NegationEngine()


def test_negation_simple_words(engine):
    assert engine.detect("Tôi không sốt", "sốt") is True
    assert engine.detect("Tôi chưa khó thở", "khó thở") is True
    assert engine.detect("Tôi không hề đau ngực", "đau ngực") is True
    assert engine.detect("Tôi không thấy tê chân", "tê chân") is True
    assert engine.detect("Tôi không có yếu chân", "yếu chân") is True
    assert engine.detect("Tôi không bị chóng mặt", "chóng mặt") is True


def test_positive_when_no_negation(engine):
    assert engine.detect("Tôi bị sốt cao", "sốt") is False
    assert engine.detect("Tôi thấy khó thở và đau ngực", "khó thở") is False
    assert engine.detect("Tôi thấy khó thở và đau ngực", "đau ngực") is False
    assert engine.detect("Tôi yếu hai chân từ sáng", "yếu") is False


def test_negation_respects_contrast_clause_boundaries(engine):
    # "nhưng" resets the negation scope
    text1 = "Tôi đau lưng nhưng không yếu chân"
    assert engine.detect(text1, "yếu chân") is True
    assert engine.detect(text1, "đau lưng") is False

    text2 = "Không khó thở nhưng đau ngực"
    assert engine.detect(text2, "khó thở") is True
    assert engine.detect(text2, "đau ngực") is False

    text3 = "Không sốt nhưng đau đầu nhiều"
    assert engine.detect(text3, "sốt") is True
    assert engine.detect(text3, "đau đầu") is False


def test_extract_multiple_terms(engine):
    text = "Tôi đau lưng nhưng không yếu chân và không sốt"
    terms = ["đau lưng", "yếu chân", "sốt"]
    extracted = engine.extract(text, terms)
    assert extracted["đau lưng"] is True
    assert extracted["yếu chân"] is False
    assert extracted["sốt"] is False


def test_severity_booster_not_treated_as_negation(engine):
    text = "Cơn đau đầu dữ dội chưa từng bị trước đây"
    # Here "chưa từng bị" describes the severity/novelty of the headache, not absence of headache
    assert engine.detect(text, "đau đầu") is False
