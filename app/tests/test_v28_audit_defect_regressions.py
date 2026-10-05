"""Real API regressions under the production-shaped unavailable gateway path."""
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services import chat
from app.services.answer_agents import AnswerAgentConfig, AnswerAgentPipeline
from app.services.agent_provider import OpenAIResponsesProvider
from app.services.circuit import CircuitBreaker
from app.services.clinical_text import normalize_search_text
from app.services.professional_response_gate import evaluate_professional_response
from app.services.semantic_risk import semantic_risk_evaluator
from app.services.toxicology_signature_router import route_by_toxicity_signature
from scripts.audit_v28_output_quality import display_projection


@pytest.fixture
def ask(monkeypatch):
    monkeypatch.setattr(chat, "settings", replace(chat.settings,
        agent_mode="enforced", agent_sync_enabled=True, agent_coverage_scope="all"))
    monkeypatch.setattr(chat, "answer_agent_pipeline", AnswerAgentPipeline(
        config=AnswerAgentConfig(mode="enforced", research_model=None, verifier_model=None),
        research_provider=OpenAIResponsesProvider(api_key=None, base_url="http://unavailable.invalid", timeout_seconds=1),
        verifier_provider=OpenAIResponsesProvider(api_key=None, base_url="http://unavailable.invalid", timeout_seconds=1),
        circuit=CircuitBreaker()))
    monkeypatch.setattr(chat.background_agent_runner, "submit", lambda **kwargs: False)
    monkeypatch.setattr(chat.active_learning_store, "capture_case", lambda **kwargs: None)
    with TestClient(create_app()) as client:
        def request(text):
            token = uuid4().hex
            response = client.post("/v1/chat", headers={"X-API-Key": "demo-key",
                "X-Tenant-Id": "tenant-demo", "Idempotency-Key": token,
                "X-Consent-Token": "consent-synthetic-regression"}, json={
                "conversation_id": token, "messages": [{"role": "user", "content": text}]})
            assert response.status_code == 200
            return response.json()
        yield request


@pytest.mark.parametrize("question,urgency", [
    ("Tôi hơi khó thở, vẫn nói chuyện bình thường, không đau ngực, không tím môi.", "URGENT"),
    ("Tôi hơi khó thở nhưng không tiếp xúc hóa chất, chất tẩy rửa hay khí độc", "URGENT"),
    ("Tôi đang khó thở dữ dội, không nói được cả câu và môi tím.", "EMERGENCY"),
    ("Tôi hít mùi clo trong phòng kín và bây giờ khó thở nhiều", "EMERGENCY"),
    ("Tôi hơi khó thở và đang đau ngực dữ dội", "EMERGENCY"),
    ("Tôi đang nổi mề đay nhẹ. Nếu sau đó sưng môi hoặc khó thở thì phải làm gì?", "ROUTINE"),
    ("Sau khi uống thuốc tôi nổi mề đay, sưng môi và đang khó thở", "EMERGENCY"),
    ("Tôi đau cơ toàn thân, không tập gym và không vận động nặng mấy ngày nay", "ROUTINE"),
    ("Tôi đau lưng nhưng không bí tiểu và không yếu chân", "ROUTINE"),
    ("Tôi đau lưng và từ sáng buồn tiểu nhưng không tiểu được", "EMERGENCY"),
])
def test_context_and_real_emergency_controls(ask, question, urgency):
    body = ask(question)
    assert body["result"]["urgency"] == urgency
    shown = display_projection(body)
    assert "suy hô hấp cấp tính" not in shown["text"].lower()
    assert "thuốc giãn phế quản tác dụng nhanh nếu có" not in shown["text"].lower()
    assert "Mã ưu tiên nội bộ" not in shown["text"]
    assert evaluate_professional_response(narrative_blocks=shown["blocks"], urgency=urgency).passed


@pytest.mark.parametrize("question,intent,required", [
    ("Tôi đang uống warfarin. Tôi có thể uống ibuprofen khi đau đầu không?", "safety", "chảy máu"),
    ("Tôi quên uống thuốc huyết áp sáng nay. Tôi có nên uống gấp đôi vào tối nay không?", "safety", "không tự tăng liều"),
    ("Tôi có thể uống thuốc của người nhà vì chúng tôi có triệu chứng giống nhau không?", "safety", "không dùng thuốc của người khác"),
    ("Tôi 20 tuổi, cao 1m70, nặng 70 kg. Tôi muốn tăng cơ. Tôi nên ăn như thế nào?", "general", "protein"),
    ("Tôi bị ho 3 ngày, có đờm nhưng không sốt. Có cần uống kháng sinh không?", "triage", "không tự dùng kháng sinh"),
    ("Tôi bị tiêu chảy 5 lần hôm nay. Tôi nên ăn uống như thế nào?", "triage", "bù nước"),
    ("Vitamin C liều cao có chữa được cảm cúm không?", "general", "bằng chứng"),
    ("Tôi sờ thấy một cục ở cổ. Có phải ung thư không?", "general", "nhiều nguyên nhân"),
    ("Tôi gửi ảnh vết thương, bạn có thể khẳng định nó bị nhiễm trùng không?", "general", "không thể khẳng định"),
])
def test_actual_question_survives_unavailable_gateway(ask, question, intent, required):
    body = ask(question)
    assert body["intent"] == intent
    assert normalize_search_text(required) in normalize_search_text(display_projection(body)["text"])


def test_education_never_replaces_present_emergency(ask):
    body = ask("Tôi muốn tăng cơ, ăn gì? Nhưng hiện đang đau ngực dữ dội và khó thở.")
    assert body["intent"] == "triage"
    assert body["result"]["urgency"] == "EMERGENCY"


def test_anticoagulant_head_trauma_still_requires_emergency(ask):
    body = ask("Tôi dùng warfarin, vừa ngã đập đầu xuống nền và đau đầu.")
    assert body["result"]["urgency"] == "EMERGENCY"


def test_anticoagulant_new_severe_headache_is_not_downgraded(ask):
    body = ask("Tôi dùng warfarin và đang đau đầu dữ dội mới xuất hiện.")
    assert body["result"]["urgency"] == "EMERGENCY"


def test_negated_severe_headache_does_not_create_anticoagulant_syndrome():
    result = semantic_risk_evaluator.evaluate("Tôi dùng warfarin nhưng không đau đầu dữ dội.")
    assert result.urgency != "EMERGENCY"


def test_negated_exposure_list_does_not_create_legacy_toxicology_signature():
    result = route_by_toxicity_signature("Tôi hơi khó thở nhưng không tiếp xúc hóa chất, chất tẩy rửa hay khí độc")
    assert not result.is_toxicology_eligible
