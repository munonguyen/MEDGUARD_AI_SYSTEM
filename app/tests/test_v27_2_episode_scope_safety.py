from app.models.chat import ChatMessage, ChatRequest
from app.services import chat
from app.services.risk_memory import infer_episode_domain


def _request(*messages: str) -> ChatRequest:
    return ChatRequest(
        conversation_id="v27-2-allergic-airway",
        messages=[ChatMessage(role="user", content=value) for value in messages],
    )


def test_lip_swelling_phrase_is_not_misread_as_neck_fatigue() -> None:
    # After diacritic stripping, Vietnamese "môi có" becomes "moi co".
    # It must never match the old generic neck-fatigue marker "mỏi cổ".
    assert infer_episode_domain("Sưng môi có vẻ bớt một chút nhưng cổ họng vẫn khó chịu.") != "musculoskeletal_spine"


def test_explicit_neck_shoulder_phrase_still_routes_to_spine_domain() -> None:
    assert infer_episode_domain("Tôi đau cổ vai gáy sau khi ngồi lâu.") == "musculoskeletal_spine"


def test_allergic_airway_improvement_keeps_previous_episode_context() -> None:
    payload = _request(
        "Sau khi uống thuốc mới tôi nổi vài mảng mề đay ở cánh tay.",
        "Ban đang lan thêm lên ngực nhưng tôi vẫn thở bình thường.",
        "Môi bắt đầu sưng và tôi thấy khó thở, cổ họng như bị nghẹn.",
        "Sưng môi có vẻ bớt một chút nhưng cổ họng vẫn khó chịu.",
    )
    latest = payload.messages[-1].content
    episode_text, context_used, switched = chat._triage_episode_text(payload, latest)
    assert context_used is True
    assert switched is False
    lowered = episode_text.lower()
    assert "khó thở" in lowered
    assert "cổ họng như bị nghẹn" in lowered
    assert "sưng môi có vẻ bớt" in lowered
