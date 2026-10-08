from threading import Event
from types import SimpleNamespace

import pytest

from app.services import chat
from app.services.bounded_agent_executor import BoundedAgentExecutor, AgentCapacityError
from app.services.clinical_safety_floor import evaluate_clinical_safety_floor
from app.services.risk_memory import should_start_new_episode
from app.tests.test_v28_audit_defect_regressions import ask


@pytest.mark.parametrize("latest", [
    "Tôi đang đau ruột thừa có nên đi mổ sớm không",
    "toi dang dau ruot thua co nen di mo som khong",
    "Tôi đang đau hố chậu phải",
])
def test_appendix_is_a_new_episode(latest):
    assert should_start_new_episode(latest, "tôi đang đau răng cần làm gì để khỏi")


def test_current_appendix_pain_has_urgent_floor():
    assert evaluate_clinical_safety_floor("Tôi đang đau ruột thừa có nên đi mổ sớm không").disposition in {"URGENT", "EMERGENCY"}
    assert evaluate_clinical_safety_floor("Tôi đang đau ruột thừa. Nếu sốt thì làm gì?").disposition in {"URGENT", "EMERGENCY"}


def test_mild_headache_is_not_mistaken_for_baldness_episode():
    from app.services.risk_memory import infer_episode_domain
    assert infer_episode_domain("Tôi hơi đau đầu từ sáng") == "neurovestibular"
    assert infer_episode_domain("Tôi bị hói đầu") == "hair_scalp"
    assert not should_start_new_episode("Giờ đau đầu dữ dội đột ngột", "Tôi hơi đau đầu từ sáng")


@pytest.mark.parametrize("question", [
    "Tôi không đau ruột thừa, chỉ hỏi để tìm hiểu",
    "Nếu đau ruột thừa thì có cần mổ không?",
    "Năm ngoái tôi đau ruột thừa nhưng đã khỏi",
])
def test_educational_or_negated_appendix_is_not_current_pain(question):
    from app.services.clinical_safety_floor import reports_current_appendix_pain
    assert not reports_current_appendix_pain(question)


def test_appendix_question_never_reuses_dental_answer(ask):
    body = ask("Tôi đang đau ruột thừa có nên đi mổ sớm không", history=[
        {"role": "user", "content": "Tôi bị đau ngực lan tay trái và khó thở, cần hỗ trợ ngay."},
        {"role": "assistant", "content": "Gọi 115 ngay."},
        {"role": "user", "content": "tôi đang đau răng cần làm gì để khỏi"},
        {"role": "assistant", "content": "Đau răng — giảm đau tạm thời và khám nha sĩ"},
    ])
    assert body["result"]["urgency"] in {"URGENT", "EMERGENCY"}
    assert body["result"]["recommended_specialty"]["code"] == "SURGERY"
    assert "nha sĩ" not in str(body["answer"])
    assert "răng" not in str(body["answer"])
    assert body["verification_status"] == "unavailable"
    assert body["answer_origin"] == "deterministic_fallback"
    assert body["agent_execution"] == {"requested": True, "writer": "not_run", "reviewer": "not_run", "reason": "configuration_incomplete"}
    assert "chỉ định mổ qua tin nhắn" in body["answer"]["summary"]


def test_agent_gets_active_episode_only(ask, monkeypatch):
    seen = []
    original = chat.answer_agent_pipeline.generate_response
    def capture(**kwargs):
        seen.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(chat.answer_agent_pipeline, "generate_response", capture)
    ask("Tôi đang đau ruột thừa có nên đi mổ sớm không", history=[
        {"role": "user", "content": "Tôi đau răng"},
        {"role": "assistant", "content": "Khám nha sĩ"},
    ])
    assert len(seen) == 1
    assert "răng" not in str(seen[0]["patient_context"]["conversation_messages"])
    assert seen[0]["patient_context"]["last_result"] is None


def test_capacity_survives_caller_timeout_and_recovers():
    release = Event()
    started = Event()
    executor = BoundedAgentExecutor(max_workers=1, max_pending=1)
    def blocked():
        started.set()
        release.wait(2)
    try:
        future = executor.submit(blocked)
        assert started.wait(1)
        assert not future.cancel()
        with pytest.raises(AgentCapacityError):
            executor.submit(lambda: None)
        release.set()
        future.result(timeout=1)
        assert executor.submit(lambda: 7).result(timeout=1) == 7
    finally:
        release.set()
        executor.shutdown(wait=True)


def test_emergency_survives_unavailable_agent(ask):
    body = ask("Tôi bị đau ngực lan tay trái và khó thở, cần hỗ trợ ngay.")
    assert body["result"]["urgency"] == "EMERGENCY"
    assert "115" in body["reply"]
    assert body["agent_execution"]["requested"]
    assert body["verification_status"] != "verified"


def test_emergency_survives_agent_capacity_rejection(ask, monkeypatch):
    from app.services import answer_agents
    from app.services.answer_agents import AnswerAgentConfig, AnswerAgentPipeline
    from app.services.circuit import CircuitBreaker
    class FullExecutor:
        def submit(self, operation):
            raise AgentCapacityError("agent_capacity_exhausted")
    monkeypatch.setattr(answer_agents, "_AGENT_EXECUTOR", FullExecutor())
    provider = SimpleNamespace(is_configured=True)
    monkeypatch.setattr(chat, "answer_agent_pipeline", AnswerAgentPipeline(
        config=AnswerAgentConfig(mode="enforced", research_model="writer", verifier_model="reviewer"),
        research_provider=provider, verifier_provider=provider, circuit=CircuitBreaker(),
    ))
    body = ask("Tôi bị đau ngực lan tay trái và khó thở, cần hỗ trợ ngay.")
    assert body["result"]["urgency"] == "EMERGENCY"
    assert "115" in body["reply"]
    assert body["agent_execution"] == {"requested": True, "writer": "not_run", "reviewer": "not_run", "reason": "capacity_exhausted"}
    assert body["verification_status"] == "unavailable"


def test_canceled_pending_work_releases_admission():
    release = Event()
    started = Event()
    executor = BoundedAgentExecutor(max_workers=1, max_pending=2)
    def blocked():
        started.set()
        release.wait(2)
    try:
        running = executor.submit(blocked)
        assert started.wait(1)
        pending = executor.submit(lambda: 1)
        assert pending.cancel()
        replacement = executor.submit(lambda: 2)
        release.set()
        running.result(timeout=1)
        assert replacement.result(timeout=1) == 2
    finally:
        release.set()
        executor.shutdown(wait=True)
