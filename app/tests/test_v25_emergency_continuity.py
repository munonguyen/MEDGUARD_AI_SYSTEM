from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _headers(key: str) -> dict[str, str]:
    return {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "X-Consent-Token": "consent-v25-emergency-continuity",
        "Idempotency-Key": key,
    }


def _chat(conversation_id: str, key: str, user_turns: list[str]):
    return client.post(
        "/v1/chat",
        headers=_headers(key),
        json={
            "conversation_id": conversation_id,
            "messages": [{"role": "user", "content": text} for text in user_turns],
        },
    )


def _assert_emergency_action_first(body: dict) -> None:
    assert body["intent"] == "triage"
    assert body["status"] == "answered"
    result = body.get("result") or {}
    assert result.get("urgency") == "EMERGENCY"
    assert result.get("emergency_flag") is True
    answer = body.get("answer") or {}
    assert answer.get("display_questions") == []
    text = " ".join(
        [answer.get("summary") or ""]
        + list(answer.get("next_steps") or [])
        + list(answer.get("safety_notes") or [])
    ).lower()
    assert "115" in text or "cấp cứu" in text


def test_severe_rigid_abdomen_turn_becomes_emergency_from_multiturn_episode():
    response = _chat(
        "v25-continuity-abdomen-t3",
        "v25-continuity-abdomen-t3",
        [
            "Tôi đau âm ỉ quanh rốn từ sáng nay.",
            "Đau chuyển xuống bụng dưới bên phải và tôi hơi sốt.",
            "Cơn đau giờ rất dữ dội, bụng cứng và tôi choáng muốn ngất.",
        ],
    )
    assert response.status_code == 200
    _assert_emergency_action_first(response.json())


def test_severe_abdominal_emergency_stays_sticky_after_partial_relief():
    response = _chat(
        "v25-continuity-abdomen-t4",
        "v25-continuity-abdomen-t4",
        [
            "Tôi đau âm ỉ quanh rốn từ sáng nay.",
            "Đau chuyển xuống bụng dưới bên phải và tôi hơi sốt.",
            "Cơn đau giờ rất dữ dội, bụng cứng và tôi choáng muốn ngất.",
            "Tôi vừa nôn xong thấy đỡ choáng hơn, có nên tự theo dõi ở nhà không?",
        ],
    )
    assert response.status_code == 200
    _assert_emergency_action_first(response.json())


def test_true_syncope_stays_emergency_even_after_full_subjective_recovery():
    response = _chat(
        "v25-continuity-syncope-t4",
        "v25-continuity-syncope-t4",
        [
            "Sáng nay tôi hơi choáng khi đứng lên nhanh.",
            "Tôi còn cảm thấy tim đập nhanh khoảng vài phút.",
            "Vừa rồi tôi ngất hẳn khoảng một phút và người nhà phải gọi mới tỉnh.",
            "Giờ tôi tỉnh táo hoàn toàn rồi, liệu chỉ cần uống nước là được?",
        ],
    )
    assert response.status_code == 200
    _assert_emergency_action_first(response.json())


def test_uncontrolled_bleeding_turn_becomes_emergency_after_failed_direct_pressure():
    response = _chat(
        "v25-continuity-bleeding-t3",
        "v25-continuity-bleeding-t3",
        [
            "Tôi bị dao cắt vào ngón tay, vết khoảng 1 cm.",
            "Tôi đã rửa và ép gạc nhưng vẫn rỉ máu.",
            "Sau 20 phút ép liên tục máu vẫn chảy nhiều và thấm ướt gạc.",
        ],
    )
    assert response.status_code == 200
    _assert_emergency_action_first(response.json())


def test_uncontrolled_bleeding_emergency_stays_sticky_when_flow_slows():
    response = _chat(
        "v25-continuity-bleeding-t4",
        "v25-continuity-bleeding-t4",
        [
            "Tôi bị dao cắt vào ngón tay, vết khoảng 1 cm.",
            "Tôi đã rửa và ép gạc nhưng vẫn rỉ máu.",
            "Sau 20 phút ép liên tục máu vẫn chảy nhiều và thấm ướt gạc.",
            "Tôi đổi gạc mới thấy chảy chậm hơn, có thể ngừng ép không?",
        ],
    )
    assert response.status_code == 200
    _assert_emergency_action_first(response.json())


def test_fever_neck_stiffness_plus_photophobia_and_slow_response_is_emergency():
    response = _chat(
        "v25-continuity-meningeal-t3",
        "v25-continuity-meningeal-t3",
        [
            "Tôi sốt 38.5 và đau đầu từ tối qua.",
            "Sáng nay đau đầu tăng và cổ bắt đầu cứng.",
            "Tôi rất sợ ánh sáng và người nhà bảo tôi trả lời chậm hơn bình thường.",
        ],
    )
    assert response.status_code == 200
    _assert_emergency_action_first(response.json())
