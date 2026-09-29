from __future__ import annotations

import pytest

from app.knowledge.loader import knowledge
from app.services.clinical_text import normalize_clinical_concepts
from app.services.rules import _check_red_flag_patterns, triage_rules


EMERGENCY_CASES = (
    (
        "V25-RF-ACUTE-ABDOMEN-001",
        "Cơn đau bụng giờ rất dữ dội, bụng cứng và tôi choáng muốn ngất.",
    ),
    (
        "V25-RF-THERMAL-AIRWAY-001",
        "Hơi nóng phả vào mặt lúc bị bỏng và giờ tôi bị khàn tiếng.",
    ),
    (
        "V25-RF-UNCONTROLLED-BLEEDING-001",
        "Tôi bị chảy máu ở tay; đã ép gạc liên tục nhưng máu vẫn chảy nhiều và thấm ướt gạc.",
    ),
    (
        "V25-RF-LIMB-ISCHEMIA-001",
        "Bàn chân bên đau lạnh hơn, các ngón chân tím và tôi khó cử động.",
    ),
    (
        "V25-RF-SUDDEN-VISION-LOSS-001",
        "Thị lực mắt trái đột ngột mờ hẳn đi trong khoảng 10 phút.",
    ),
    (
        "V25-RF-MENINGEAL-AMS-001",
        "Tôi sốt, cổ cứng, rất sợ ánh sáng và người nhà bảo tôi trả lời chậm hơn bình thường.",
    ),
    (
        "V25-RF-HEAT-CNS-001",
        "Tôi vừa chạy ngoài trời nóng; bạn tôi nói tôi bắt đầu lú lẫn và đi không vững.",
    ),
    (
        "V25-RF-CHEMICAL-INHALATION-001",
        "Tôi vừa hít phải hóa chất trong phòng kín và bây giờ khó thở, tức ngực.",
    ),
    (
        "V25-RF-PREGNANCY-ECTOPIC-001",
        "Tôi đang mang thai khoảng 8 tuần, đau lệch một bên bụng dưới, giờ choáng và đau vai.",
    ),
    (
        "V25-RF-SEVERE-AIRFLOW-001",
        "Tôi khò khè, giờ thở rất gấp và không nói trọn câu được.",
    ),
    (
        "V25-RF-TACHYCARDIA-PRESYNCOPE-001",
        "Nhịp tim 145 lần/phút và tôi gần ngất.",
    ),
    (
        "V25-RF-DEHYDRATION-COLLAPSE-001",
        "Tôi nôn và tiêu chảy, không giữ được nước, vừa gần ngất và tim đập rất nhanh.",
    ),
)


@pytest.mark.parametrize(("expected_id", "text"), EMERGENCY_CASES)
def test_v25_compositional_overlay_promotes_complete_emergency_patterns(expected_id: str, text: str):
    normalized = normalize_clinical_concepts(text)
    matched = _check_red_flag_patterns(normalized)
    matched_ids = {str(item.get("id")) for item in matched}

    assert expected_id in matched_ids

    result = triage_rules(text)
    assert result.urgency == "EMERGENCY"
    assert result.emergency_flag is True
    assert result.clarifying_questions == []


def test_v25_safety_overlay_is_versioned_and_in_integrity_report():
    assert "v25_safety_overlay.json" in knowledge.files
    assert knowledge.files["v25_safety_overlay.json"].version == "25.4.0"
    assert "v25_safety_overlay.json" in knowledge.integrity_report()


@pytest.mark.parametrize(
    "text",
    (
        "Tôi khàn tiếng sau cảm lạnh, không hít khói hay hơi nóng và vẫn thở bình thường.",
        "Bàn chân hơi lạnh sau khi ngồi điều hòa nhưng cử động bình thường, không tê yếu.",
        "Tôi sốt và đau đầu nhưng cổ mềm, tỉnh táo, không sợ ánh sáng.",
        "Tôi vừa chạy ngoài trời nóng nhưng hoàn toàn tỉnh táo và đi đứng bình thường.",
        "Tôi bị vết cắt nhỏ, đã ép gạc và máu đã cầm hoàn toàn.",
        "Tôi mang thai 8 tuần, hơi đau bụng lan tỏa nhưng không choáng, không đau vai và không ra máu.",
    ),
)
def test_v25_overlay_does_not_fire_when_required_composition_is_absent_or_negated(text: str):
    normalized = normalize_clinical_concepts(text)
    matched_ids = {
        str(item.get("id"))
        for item in _check_red_flag_patterns(normalized)
        if str(item.get("id", "")).startswith("V25-RF-")
    }

    assert matched_ids == set()
