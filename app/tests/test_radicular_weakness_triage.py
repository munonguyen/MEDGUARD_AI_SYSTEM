"""Clinical validation test for lumbar radiculopathy progression and booking triage."""

import pytest
from app.models.chat import ChatMessage, ChatRequest, ChatContext
from app.services.chat import orchestrate_chat
from app.core.context import RequestContext


@pytest.fixture
def req_ctx():
    return RequestContext(request_id="test-radic-flow", tenant_id="t1", idempotency_key="k1")


def test_lumbar_radiculopathy_progression_and_booking_guard(req_ctx):
    # Turn 1: Sitting back pain
    req1 = ChatRequest(
        conversation_id="conv-radic-1",
        messages=[ChatMessage(role="user", content="Tôi bị đau thắt lưng do ngồi làm việc máy tính nhiều.")],
        context=ChatContext(age=35, sex="male"),
        locale="vi",
    )
    resp1 = orchestrate_chat(req1, req_ctx)
    res1 = resp1.result or {}
    assert resp1.intent == "triage"
    assert res1.get("urgency") == "ROUTINE"
    spec1 = res1.get("recommended_specialty") or {}
    assert spec1.get("code") == "ORTHOPEDICS" or spec1.get("label") == "Cơ xương khớp"

    # Turn 2: Radiating pain + numbness with normal motor strength
    req2 = ChatRequest(
        conversation_id="conv-radic-1",
        messages=[
            ChatMessage(role="user", content="Tôi bị đau thắt lưng do ngồi làm việc máy tính nhiều."),
            ChatMessage(role="assistant", content=resp1.reply),
            ChatMessage(role="user", content="Tôi chỉ bị tê và đau dọc xuống chân chứ lực chân vẫn bình thường."),
        ],
        context=ChatContext(age=35, sex="male"),
        locale="vi",
    )
    resp2 = orchestrate_chat(req2, req_ctx)
    res2 = resp2.result or {}
    assert resp2.intent == "triage"
    assert res2.get("urgency") == "URGENT"
    spec2 = res2.get("recommended_specialty") or {}
    assert spec2.get("code") == "ORTHOPEDICS" or spec2.get("label") == "Cơ xương khớp"

    # Turn 3: Weak leg / difficult to lift leg
    req3 = ChatRequest(
        conversation_id="conv-radic-1",
        messages=[
            ChatMessage(role="user", content="Tôi bị đau thắt lưng do ngồi làm việc máy tính nhiều."),
            ChatMessage(role="assistant", content=resp1.reply),
            ChatMessage(role="user", content="Tôi chỉ bị tê và đau dọc xuống chân chứ lực chân vẫn bình thường."),
            ChatMessage(role="assistant", content=resp2.reply),
            ChatMessage(role="user", content="Tôi cảm thấy chân hơi yếu, khó nhấc chân lên khi đi lại."),
        ],
        context=ChatContext(age=35, sex="male"),
        locale="vi",
    )
    resp3 = orchestrate_chat(req3, req_ctx)
    res3 = resp3.result or {}
    assert resp3.intent == "triage"
    assert res3.get("urgency") == "URGENT"
    spec3 = res3.get("recommended_specialty") or {}
    assert spec3.get("code") == "ORTHOPEDICS" or spec3.get("label") == "Cơ xương khớp"
    
    # Must NOT mention stroke or TIA
    lower_reply = resp3.reply.lower()
    assert "đột quỵ" not in lower_reply
    assert "nhồi máu não" not in lower_reply
    assert "tai biến" not in lower_reply
    assert "cơn thiếu máu não" not in lower_reply

    # Must contain cauda equina screening questions or warnings
    assert any(term in lower_reply for term in ("bí tiểu", "tiểu không tự chủ", "yên ngựa", "mất kiểm soát"))

    # Turn 4: Booking appointment in urgent radiculopathy state
    req4 = ChatRequest(
        conversation_id="conv-radic-1",
        messages=[
            ChatMessage(role="user", content="Tôi bị đau thắt lưng do ngồi làm việc máy tính nhiều."),
            ChatMessage(role="assistant", content=resp1.reply),
            ChatMessage(role="user", content="Tôi chỉ bị tê và đau dọc xuống chân chứ lực chân vẫn bình thường."),
            ChatMessage(role="assistant", content=resp2.reply),
            ChatMessage(role="user", content="Tôi cảm thấy chân hơi yếu, khó nhấc chân lên khi đi lại."),
            ChatMessage(role="assistant", content=resp3.reply),
            ChatMessage(role="user", content="Xem lịch ca khám và bác sĩ Cơ xương khớp hôm nay"),
        ],
        context=ChatContext(age=35, sex="male"),
        locale="vi",
    )
    resp4 = orchestrate_chat(req4, req_ctx)
    res4 = resp4.result or {}
    assert resp4.intent == "appointment_search"
    assert res4.get("urgency") == "URGENT"
    assert res4.get("slots_available") is True
    assert "DEMO" in resp4.reply or "MÔ PHỎNG" in resp4.reply


def test_emergency_state_blocks_routine_appointment(req_ctx):
    # Patient with acute stroke symptoms asking for routine appointment
    req = ChatRequest(
        conversation_id="conv-emg-block",
        messages=[
            ChatMessage(role="user", content="Bố tôi bị méo miệng và liệt nửa người đột ngột"),
            ChatMessage(role="assistant", content="Cần gọi 115 ngay"),
            ChatMessage(role="user", content="Tôi muốn xem lịch bác sĩ để đặt khám"),
        ],
        context=ChatContext(age=65, sex="male"),
        locale="vi",
    )
    resp = orchestrate_chat(req, req_ctx)
    res = resp.result or {}
    # Emergency should override routine slots
    assert res.get("slots_available") is not True
    assert "115" in resp.reply or "cấp cứu" in resp.reply.lower()
