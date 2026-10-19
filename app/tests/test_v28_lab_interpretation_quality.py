from app.models.clinical_task import ClinicalTask
from app.services.clinical_task_router import resolve_clinical_task
from app.services.lab_interpreter import interpret_laboratory_text


def test_alt_high_is_explained_without_diagnosing_liver_disease():
    question = "Xét nghiệm máu của tôi có ALT cao. Điều đó có nghĩa là tôi bị bệnh gan không?"
    task = resolve_clinical_task(question)
    result = interpret_laboratory_text(question)

    assert task.task == ClinicalTask.LAB_INTERPRETATION
    assert result.urgency == "ROUTINE"
    assert result.confidence >= 0.60
    combined = " ".join((result.summary, *result.interpretation_points)).lower()
    assert "không đồng nghĩa" in combined or "không đủ" in combined
    assert "bệnh gan" in combined
    assert "alt" in combined


def test_fasting_glucose_is_lab_interpretation_not_acute_monitoring_only():
    question = "Đường huyết lúc đói của tôi là 7,2 mmol/L. Có phải tôi bị tiểu đường không?"
    task = resolve_clinical_task(question)
    result = interpret_laboratory_text(question)

    assert task.task == ClinicalTask.LAB_INTERPRETATION
    assert result.urgency == "ROUTINE"
    assert result.confidence >= 0.80
    assert result.observations[0].test_name == "fasting_glucose"
    assert result.observations[0].value_numeric == 7.2
    combined = " ".join((result.summary, *result.interpretation_points)).lower()
    assert "7,0" in combined
    assert "xác nhận" in combined
    assert "không" in combined and "chẩn đoán" in combined
