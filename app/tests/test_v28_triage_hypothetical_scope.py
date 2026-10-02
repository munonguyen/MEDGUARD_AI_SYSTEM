from app.core.context import RequestContext
from app.models.triage import TriageRequest
from app.services.triage import evaluate_triage


CTX = RequestContext(
    request_id="req-v28-hypothetical",
    tenant_id="tenant-demo",
    idempotency_key="v28-hypothetical",
)


def _evaluate(text: str, *, conversation_risk: str | None = None):
    return evaluate_triage(
        TriageRequest(patient_ref="V28-TEST", symptoms_text=text),
        CTX,
        conversation_risk=conversation_risk,
    )


def test_pure_hypothetical_airway_question_is_not_current_emergency():
    result = _evaluate("Nếu bắt đầu sưng môi hoặc khó thở thì tôi phải làm gì?")
    assert result.urgency == "ROUTINE"
    assert result.emergency_flag is False
    assert result.trace.details["hypothetical_scope_applied"] is True
    assert result.trace.details["current_analysis_text_present"] is False
    assert "giả định" in result.advice
    assert "Nếu sưng môi/lưỡi" in result.advice


def test_current_rash_plus_hypothetical_airway_warning_is_not_current_emergency():
    result = _evaluate(
        "Tôi đang nổi mề đay ở cánh tay, nếu sưng môi hoặc khó thở thì tôi phải làm gì?"
    )
    assert result.emergency_flag is False
    assert result.trace.details["hypothetical_scope_applied"] is True
    assert result.trace.details["current_analysis_text_present"] is True


def test_actual_airway_allergy_remains_emergency():
    result = _evaluate(
        "Sau khi uống thuốc mới tôi nổi mề đay, môi bắt đầu sưng và thấy khó thở"
    )
    assert result.urgency == "EMERGENCY"
    assert result.emergency_flag is True
    assert result.trace.details["hypothetical_scope_applied"] is False


def test_historical_emergency_floor_is_not_erased_by_hypothetical_scope():
    result = _evaluate(
        "Nếu triệu chứng quay lại thì tôi phải làm gì?",
        conversation_risk="EMERGENCY",
    )
    assert result.urgency == "EMERGENCY"
    assert result.emergency_flag is True
