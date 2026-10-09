import asyncio
from concurrent.futures import Future
from contextvars import copy_context
from types import SimpleNamespace

import pytest
from threading import BoundedSemaphore
from fastapi import HTTPException

from app.api.routes import prepared_chat_speech
from app.core.context import RequestContext
from app.models.chat import ChatRequest, ChatResponse, GroundedAnswer, AnswerNarrativeBlock
import app.services.companion_voice as voice


def response(text="Bạn cần đo nhiệt độ.", status="verified"):
    return ChatResponse(request_id="r", conversation_id="c", status="answered", intent="triage",
                        reply=text, spoken_reply=text, verification_status=status)


def preparation(text="Bạn cần đo nhiệt độ.", ready=False):
    prepared = voice.VoicePreparation("dr_tuan")
    prepared.text = text
    prepared.future = Future()
    if ready:
        prepared.future.set_result(b"ID3approved")
    return prepared


@pytest.fixture(autouse=True)
def cleanup_tickets():
    yield
    with voice._tickets_lock:
        voice._tickets.clear()


def test_no_audio_release_before_all_gates_or_after_prefix_revision():
    for status in ("rejected", "unavailable", "shadow_pending", "error", "not_requested"):
        assert preparation(ready=True).approve(response(status=status), "tenant-a") is None
    assert preparation(ready=True).approve(response("Câu đầu đã được sửa."), "tenant-a") is None
    assert not voice._tickets


def test_approval_does_not_wait_for_tts_and_reuses_same_future():
    prepared = preparation()
    metadata = prepared.approve(response(), "tenant-a")
    assert metadata and not prepared.future.done()
    assert voice.claim_speech(metadata["ticket"], "tenant-b") is None
    entry = voice.claim_speech(metadata["ticket"], "tenant-a")
    assert entry.future is prepared.future
    assert voice.claim_speech(metadata["ticket"], "tenant-a") is None
    prepared.future.set_result(b"ID3approved")
    assert entry.future.result() == b"ID3approved"


def test_ticket_expiry_and_failed_preparation_are_not_released(monkeypatch):
    prepared = preparation(ready=True)
    metadata = prepared.approve(response(), "tenant-a")
    voice._tickets[metadata["ticket"]].expires = 0
    assert voice.claim_speech(metadata["ticket"], "tenant-a") is None
    prepared = preparation()
    prepared.future.set_exception(RuntimeError("private upstream data"))
    assert prepared.approve(response(), "tenant-a") is None


def test_request_scope_isolated_and_closed_context_rejects_late_writer(monkeypatch):
    first, token = voice.begin_voice("dr_tuan")
    captured = copy_context()
    voice.end_voice(first, token)
    second, token2 = voice.begin_voice("dr_mai")
    try:
        captured.run(voice.prepare_writer_voice, "Late draft from cancelled turn.")
        assert first.future is None and second.future is None
    finally:
        voice.end_voice(second, token2)


def test_prepared_endpoint_returns_only_approved_tenant_audio():
    metadata = preparation(ready=True).approve(response(), "tenant-a")
    class Request:
        async def is_disconnected(self): return False
    async def run():
        with pytest.raises(HTTPException) as error:
            await prepared_chat_speech(metadata["ticket"], Request(), RequestContext("r", "tenant-b", ""), "consent")
        assert error.value.status_code == 404
        audio = await prepared_chat_speech(metadata["ticket"], Request(), RequestContext("r", "tenant-a", ""), "consent")
        assert audio.body == b"ID3approved" and audio.headers["cache-control"] == "no-store"
    asyncio.run(run())


def test_spoken_contract_keeps_warnings_and_selected_questions_without_literal_repeats():
    result = response("Bạn cần đo nhiệt độ. Theo dõi triệu chứng.")
    result.answer = GroundedAnswer(title="Theo dõi",summary=result.reply,decision_basis="versioned_rules",
        evidence_state="direct_rule_match", narrative=[AnswerNarrativeBlock(text=result.reply)],
        next_steps=["Theo dõi triệu chứng."], safety_notes=["Nếu khó thở, cần đánh giá khẩn cấp."],
        questions=["Câu hỏi cũ?"], display_questions=["Nhiệt độ đo được là bao nhiêu?"])
    spoken = voice.spoken_reply(result)
    assert spoken.count("Theo dõi triệu chứng.") == 1
    assert "Nếu khó thở" in spoken and "Nhiệt độ đo được" in spoken and "Câu hỏi cũ" not in spoken
    result.answer.display_questions = []
    assert "Câu hỏi cũ" not in voice.spoken_reply(result)


def test_segments_keep_decimal_and_limits_and_do_not_drop_text():
    text = "Bạn đo được 38.5 độ C. Cần theo dõi tiếp."
    assert voice.first_segment(text) == "Bạn đo được 38.5 độ C."
    text = "Một đoạn văn dài " * 25
    segment = voice.first_segment(text)
    assert len(segment) <= 180 and voice.plain_speech(text).startswith(segment)


def test_chat_voice_optin_keeps_tickets_out_of_persisted_response(monkeypatch):
    import app.api.routes as routes
    prepared = preparation(ready=True)
    stored = []
    monkeypatch.setattr(routes, "get_idempotent_response", lambda **_: None)
    monkeypatch.setattr(routes, "orchestrate_chat", lambda *_: response())
    monkeypatch.setattr(routes, "begin_voice", lambda _: (prepared, None))
    monkeypatch.setattr(routes, "end_voice", lambda *_: prepared.close())
    monkeypatch.setattr(routes, "store_idempotent_response", lambda **kw: stored.append(kw["response"]))
    payload = ChatRequest(conversation_id="c", messages=[{"role":"user","content":"Tôi bị sốt."}], voice={"persona":"dr_tuan"})
    result = routes.chat(payload, RequestContext("r", "tenant-a", "key"), "consent")
    assert result.prepared_speech is not None
    assert stored[0].prepared_speech is None and stored[0].spoken_reply == result.spoken_reply


def test_failed_tts_returns_safe_code_without_provider_details():
    prepared = preparation()
    metadata = prepared.approve(response(), "tenant-a")
    prepared.future.set_exception(RuntimeError("private upstream secret"))
    class Request:
        async def is_disconnected(self): return False
    async def run():
        with pytest.raises(HTTPException) as error:
            await prepared_chat_speech(metadata["ticket"], Request(), RequestContext("r", "tenant-a", ""), "consent")
        assert error.value.status_code == 503 and "secret" not in str(error.value.detail)
    asyncio.run(run())


def test_bounded_preparation_has_no_unbounded_pending_queue(monkeypatch):
    calls = []
    class Executor:
        def submit(self, operation):
            future = Future(); calls.append((operation, future)); return future
    async def synth(payload): return b"ID3test"
    monkeypatch.setattr(voice, "_workers", Executor())
    monkeypatch.setattr(voice, "_slots", BoundedSemaphore(1))
    monkeypatch.setattr(voice, "synthesize_doctor_speech", synth)
    first = voice.VoicePreparation("dr_tuan"); second = voice.VoicePreparation("dr_mai")
    first.start("First."); second.start("Second.")
    assert len(calls) == 1 and second.future is None
    operation, future = calls.pop(); future.set_result(operation())
    second.start("Second.")
    assert len(calls) == 1
    operation, future = calls.pop(); future.set_result(operation())
    first.close(); first.start("Late.")
    assert not calls


def test_writer_voice_hook_crosses_agent_thread_before_reviewer():
    from app.tests.test_answer_agents import pipeline, approved_draft, verification, baseline_answer
    prepared, token = voice.begin_voice("dr_tuan")
    calls = []
    prepared.start = lambda text: calls.append(text)
    instance, _, verifier = pipeline(approved_draft(), verification())
    original = verifier.complete
    def review(**values):
        assert calls, "TTS preparation must begin before Reviewer, not after chat returns"
        return original(**values)
    verifier.complete = review
    try:
        result = instance.enhance(answer=baseline_answer(), intent="triage", question="Tôi bị đau đầu.", request_id="prepared-hook")
        assert calls and result.agent_trace.status == "verified"
    finally:
        voice.end_voice(prepared, token)


def test_http_ticket_route_requires_credentials_and_rechecks_consent(monkeypatch):
    from dataclasses import replace
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.config import settings
    metadata = preparation(ready=True).approve(response(), "tenant-demo")
    monkeypatch.setattr("app.services.consent.settings", replace(settings, enforce_consent=True))
    path = "/v1/chat/speech/" + metadata["ticket"]
    with TestClient(app) as client:
        assert client.get(path).status_code == 400
        headers = {"X-API-Key":"demo-key", "X-Tenant-Id":"tenant-demo"}
        assert client.get(path, headers=headers).status_code == 403
        # A refusal must not consume another user's capability or the ticket.
        headers["X-Consent-Token"] = "test-consent"
        result = client.get(path, headers=headers)
        assert result.status_code == 200 and result.content == b"ID3approved"
