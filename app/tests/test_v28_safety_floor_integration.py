from app.services.clinical_safety_floor import evaluate_clinical_safety_floor


def test_exertional_chest_pressure_raises_floor_to_urgent():
    floor = evaluate_clinical_safety_floor("Tôi thấy nặng ngực khi đi bộ nhanh")
    assert floor.disposition in {"URGENT", "EMERGENCY"}
    assert "v28_clinical_context_router" in floor.sources or floor.disposition == "EMERGENCY"


def test_actual_chest_pain_with_dyspnea_and_sweating_is_emergency():
    floor = evaluate_clinical_safety_floor("Tôi đau ngực, khó thở và vã mồ hôi")
    assert floor.disposition == "EMERGENCY"


def test_back_pain_with_explicitly_negated_weakness_is_not_false_emergency():
    floor = evaluate_clinical_safety_floor("Tôi đau lưng nhưng không yếu chân")
    assert floor.disposition != "EMERGENCY"


def test_back_pain_with_weakness_and_incontinence_is_emergency():
    floor = evaluate_clinical_safety_floor(
        "Tôi đau lưng kèm yếu hai chân và mất kiểm soát tiểu tiện"
    )
    assert floor.disposition == "EMERGENCY"


def test_pure_hypothetical_airway_question_is_not_current_emergency():
    floor = evaluate_clinical_safety_floor(
        "Nếu bắt đầu sưng môi hoặc khó thở thì tôi phải làm gì?"
    )
    assert floor.disposition == "ROUTINE"
    assert "v28_clinical_context_router" in floor.sources


def test_current_rash_with_hypothetical_airway_warning_is_not_current_emergency():
    floor = evaluate_clinical_safety_floor(
        "Tôi đang nổi mề đay, nếu sưng môi hoặc khó thở thì tôi phải làm gì?"
    )
    assert floor.disposition != "EMERGENCY"


def test_real_airway_allergy_progression_still_escalates():
    floor = evaluate_clinical_safety_floor(
        "Sau khi uống thuốc mới tôi nổi mề đay, môi bắt đầu sưng và thấy khó thở"
    )
    assert floor.disposition == "EMERGENCY"
