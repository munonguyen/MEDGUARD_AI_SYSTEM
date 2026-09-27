import pytest
from app.core.context import RequestContext
from app.models.chat import ChatRequest, ChatMessage, ChatContext
from app.services.chat import orchestrate_chat


def test_back_pain_radiculopathy_contradiction_resolution():
    """Verify episode continuity, triage monotonicity (hysteresis floor), and contradiction resolution."""
    ctx = RequestContext(request_id="test-contradiction-1", tenant_id="default", idempotency_key="k-contra-1")

    history = [
        ChatMessage(role="user", content="Tôi bị đau thắt lưng sau khi vận động."),
        ChatMessage(role="assistant", content="Đã ghi nhận tình trạng đau thắt lưng. Cơn đau có lan xuống chân hoặc tê bì không?"),
        ChatMessage(role="user", content="Cơn đau có lan xuống mông và chân."),
        ChatMessage(role="assistant", content="Tình trạng đau thắt lưng lan xuống mông và chân NÊN ĐƯỢC ĐÁNH GIÁ Y TẾ SỚM tại chuyên khoa Cơ xương khớp."),
        ChatMessage(role="user", content="Cơn đau tự nhiên xuất hiện không rõ lý do"),
    ]

    req = ChatRequest(
        conversation_id="conv-contradiction-test",
        messages=history,
        context=ChatContext(age=35, sex="male"),
        locale="vi",
    )

    res = orchestrate_chat(req, ctx)

    # 1. Episode continuity: Intent remains triage, specialty remains Orthopedics
    assert res.intent == "triage"
    spec_code = res.result["recommended_specialty"]["code"] if isinstance(res.result, dict) else res.result.recommended_specialty.code
    assert spec_code == "ORTHOPEDICS"

    # 2. Triage monotonicity / safety floor: Must NOT downgrade to ROUTINE
    urgency = res.result["urgency"] if isinstance(res.result, dict) else res.result.urgency
    assert urgency == "URGENT"

    # 3. No leg trauma protocol template hijacking
    reply_lower = res.reply.lower()
    assert "lật cổ chân" not in reply_lower
    assert "chân biến dạng" not in reply_lower

    # 4. Contradiction Resolution: recognizes conflict and asks single high-information question
    assert "không rõ" in reply_lower or "tự nhiên" in reply_lower
    assert "lan xuống" in reply_lower
    assert "vận động" in reply_lower

    # Clarifying question verification: exactly 1 question with highest information gain
    assert res.answer is not None
    assert len(res.answer.questions) == 1
    assert "Bạn nhớ cơn đau bắt đầu sau vận động" in res.answer.questions[0]

    # 5. Quick-reply deduplication
    labels = [s.label.strip().lower() for s in res.suggestions]
    assert len(labels) == len(set(labels)), f"Duplicate suggestions found: {labels}"
    assert not any(labels.count(lbl) > 1 for lbl in labels)


def test_explicit_correction_permits_downgrade():
    """Verify that an explicit factual retraction invalidates the previous premise and recomputes correctly."""
    ctx = RequestContext(request_id="test-correction-1", tenant_id="default", idempotency_key="k-corr-1")

    history = [
        ChatMessage(role="user", content="Tôi bị đau thắt lưng sau khi vận động."),
        ChatMessage(role="assistant", content="Đã ghi nhận tình trạng đau thắt lưng. Cơn đau có lan xuống chân hoặc tê bì không?"),
        ChatMessage(role="user", content="Cơn đau có lan xuống mông và chân."),
        ChatMessage(role="assistant", content="Tình trạng đau thắt lưng lan xuống mông và chân NÊN ĐƯỢC ĐÁNH GIÁ Y TẾ SỚM."),
        ChatMessage(role="user", content="À tôi nhìn nhầm, không phải bị đau lan xuống chân đâu mà tôi hỏi cho người khác, còn tôi chỉ bị mỏi cơ do ngồi máy tính thôi."),
    ]

    req = ChatRequest(
        conversation_id="conv-correction-test",
        messages=history,
        context=ChatContext(age=35, sex="male"),
        locale="vi",
    )

    res = orchestrate_chat(req, ctx)
    urgency = res.result["urgency"] if isinstance(res.result, dict) else res.result.urgency
    assert urgency == "ROUTINE"
