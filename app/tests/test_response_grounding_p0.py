from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.semantic_abstraction_lattice import (
    AbstractThreatArchetype,
    evaluate_abstraction_lattice,
)
from app.services.semantic_relation_extractor import extract_semantic_relations
from app.services.clinical_text import contains_affirmed_phrase, normalize_search_text


def _archetypes(text: str):
    graph = extract_semantic_relations(text)
    return evaluate_abstraction_lattice(graph).active_archetypes


def _chat(prompt: str, key: str):
    client = TestClient(app)
    with patch("app.services.chat.background_agent_runner.submit", return_value=False), patch(
        "app.services.chat.active_learning_store.capture_case", return_value=None
    ):
        response = client.post(
            "/v1/chat",
            headers={
                "X-API-Key": "demo-key",
                "X-Tenant-Id": "tenant-demo",
                "X-Consent-Token": "consent-grounding-regression",
                "Idempotency-Key": key,
            },
            json={
                "conversation_id": key,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
    assert response.status_code == 200
    return response.json()


def _answer_text(body: dict) -> str:
    answer = body.get("answer") or {}
    values: list[str] = []
    for key in (
        "summary", "clinical_hypotheses", "key_points", "next_steps",
        "safety_notes", "questions", "limitations",
    ):
        value = answer.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value:
            values.append(str(value))
    return " ".join(values).lower()


def test_sleep_deprivation_cannot_invent_tension_headache_for_chest_pain():
    patterns = _archetypes(
        "Tôi bị đau ngực nhưng tôi nghĩ chỉ do thiếu ngủ. Tôi cứ ở nhà theo dõi được không?"
    )
    assert all(
        p.archetype != AbstractThreatArchetype.BENIGN_TENSION_HEADACHE
        for p in patterns
    )


def test_actual_tension_headache_remains_supported():
    patterns = _archetypes(
        "Tôi đau đầu âm ỉ hai bên thái dương sau mấy hôm thiếu ngủ và ngồi máy tính nhiều."
    )
    assert any(
        p.archetype == AbstractThreatArchetype.BENIGN_TENSION_HEADACHE
        for p in patterns
    )


def test_pregnancy_emergency_rationale_only_states_observed_features():
    patterns = _archetypes(
        "Tôi đang mang thai và bị đau bụng kèm chảy máu. Tôi nên làm gì?"
    )
    pregnancy = next(
        p for p in patterns
        if p.archetype == AbstractThreatArchetype.PREGNANCY_EMERGENCY
    )
    rationale = pregnancy.clinical_rationale.lower()
    assert "đang mang thai" in rationale
    assert "đau bụng" in rationale
    assert "chảy máu" in rationale
    assert "trễ kinh" not in rationale
    assert "choáng" not in rationale


def test_chat_chest_pain_sleep_deprivation_never_turns_into_headache():
    body = _chat(
        "Tôi bị đau ngực nhưng tôi nghĩ chỉ do thiếu ngủ. Tôi cứ ở nhà theo dõi được không?",
        "grounding-chest-sleep",
    )
    specialty = ((body.get("result") or {}).get("recommended_specialty") or {}).get("code")
    assert "đau đầu" not in _answer_text(body)
    assert specialty != "NEUROLOGY"


def test_pregnancy_chat_does_not_assert_unreported_dizziness_or_missed_period():
    body = _chat(
        "Tôi đang mang thai và bị đau bụng kèm chảy máu. Tôi nên làm gì?",
        "grounding-pregnancy",
    )
    text = _answer_text(body)
    assert "trễ kinh" not in text
    assert "choáng váng" not in text


def test_emergency_summary_uses_explicit_diagnostic_uncertainty():
    body = _chat(
        "Người nhà tôi có dấu hiệu méo miệng, nói khó và yếu một bên tay.",
        "grounding-stroke-uncertainty",
    )
    assert (body.get("result") or {}).get("urgency") == "EMERGENCY"
    summary = ((body.get("answer") or {}).get("summary") or "").lower()
    assert "không xác định nguyên nhân hoặc chẩn đoán" in summary
    assert "không thể khẳng định" in summary


def test_yes_no_question_does_not_promote_hypothesis_to_fact():
    text = normalize_search_text("Tôi nên chờ xem có tự hết không?")
    assert contains_affirmed_phrase(text, "tu het") is False


def test_true_resolved_tia_language_remains_affirmed():
    text = normalize_search_text("Tôi nói khó và yếu một tay khoảng 10 phút rồi tự hết hoàn toàn.")
    assert contains_affirmed_phrase(text, "tu het") is True


def test_fact_with_separate_negative_clause_is_not_mistaken_for_question():
    text = normalize_search_text("Tôi có đau ngực, không sốt.")
    assert contains_affirmed_phrase(text, "dau nguc") is True


def test_stroke_question_does_not_render_hypothetical_resolution_as_observed_fact():
    body = _chat(
        "Người nhà tôi có dấu hiệu méo miệng, nói khó và yếu một bên tay. Tôi nên chờ xem có tự hết không?",
        "grounding-stroke-question-scope",
    )
    result = body.get("result") or {}
    answer = body.get("answer") or {}
    text = _answer_text(body)
    assert result.get("urgency") == "EMERGENCY"
    assert answer.get("display_questions") == []
    assert "gọi cấp cứu 115" in text or "gọi 115" in text
    assert "[nói khó, tự hết]" not in text
    assert "[noi kho, tu het]" not in normalize_search_text(text)
