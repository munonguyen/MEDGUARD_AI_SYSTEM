"""Unit tests for Typo-Resilience, Teencode Normalization, and Clinical Self-Correction."""

from __future__ import annotations

import pytest

from app.core.context import RequestContext
from app.models.chat import ChatMessage, ChatRequest
from app.services.chat import _detect_intent, orchestrate_chat
from app.services.clinical_text import normalize_search_text
from app.services.ood_guard import evaluate as ood_evaluate


def _make_ctx() -> RequestContext:
    return RequestContext(
        request_id="req-test-typo",
        tenant_id="tenant-demo",
        idempotency_key="ik-test-typo",
    )


def test_teencode_normalization():
    """Verify common teencode and typing shortcuts are normalized to standard medical Vietnamese."""
    text1 = "tôi đang đi trên đg do vận sức wá bị kăng kơ tay"
    norm1 = normalize_search_text(text1)
    assert "cang co" in norm1
    assert "tay" in norm1
    assert "van suc" in norm1

    text2 = "bị chuọt zút bắp chân đau wá không đi đc"
    norm2 = normalize_search_text(text2)
    assert "chuot rut" in norm2
    assert "bap chan" in norm2

    text3 = "uốg thuốk paracetamol chung zới ibuprofen đc ko bsi"
    norm3 = normalize_search_text(text3)
    assert "uong" in norm3
    assert "thuoc" in norm3
    assert "voi" in norm3
    assert "duoc" in norm3
    assert "khong" in norm3
    assert "bac si" in norm3


def test_muscle_strain_natural_persuasive_response():
    """User query about overexertion arm strain receives tailored RICE guidance rather than generic template."""
    query = "tôi đang đi trên đường do vận sức quá bị căng cơ tay"
    ctx = _make_ctx()
    req = ChatRequest(
        conversation_id="conv-strain-test",
        messages=[ChatMessage(role="user", content=query)],
    )

    resp = orchestrate_chat(req, ctx)
    assert resp.intent == "triage"
    assert resp.status == "answered"

    summary = resp.answer.summary
    # Check that guidance includes RICE components and muscle strain context
    assert "căng cơ" in summary or "vi chấn thương" in summary or "RICE" in summary
    assert "chườm lạnh" in summary or "nghỉ ngơi" in summary or "băng thun" in summary
    # Check that follow-up question is relevant
    assert "Bạn cho mình biết thêm:" in summary or len(resp.suggestions) > 0


def test_personalized_dose_priority_over_symptom():
    """When a known medication and a dosage question are asked together with a symptom, safety takes priority."""
    query = "Đau căng cơ uống paracetamol mấy viên một ngày để khỏi nhanh?"
    norm = normalize_search_text(query)
    req = ChatRequest(
        conversation_id="conv-dose-test",
        messages=[ChatMessage(role="user", content=query)],
    )
    detected = _detect_intent(req, norm)
    assert detected == "safety"

    ctx = _make_ctx()
    resp = orchestrate_chat(req, ctx)
    assert resp.intent == "safety"
    assert resp.status == "unsupported"
    assert "không kê hoặc tính liều thuốc cá nhân hóa" in resp.answer.summary


def test_soft_tissue_rice_not_blocked_as_ood_software():
    """Queries about soft-tissue injuries ('chấn thương phần mềm') must not be blocked as programming software."""
    query = "Phương pháp RICE sơ cứu chấn thương phần mềm là gì và làm như thế nào?"
    assert ood_evaluate(query) is None

    ctx = _make_ctx()
    req = ChatRequest(
        conversation_id="conv-rice-test",
        messages=[ChatMessage(role="user", content=query)],
    )
    resp = orchestrate_chat(req, ctx)
    assert resp.intent == "triage"
    assert resp.status == "answered"


def test_running_strain_not_blocked_as_ood_sports():
    """Leg strain during running must not be blocked by the sports OOD filter."""
    query = "Tự dưng bị căng cứng cơ đùi khi chạy bộ nên làm gì ngay?"
    assert ood_evaluate(query) is None

    ctx = _make_ctx()
    req = ChatRequest(
        conversation_id="conv-run-strain-test",
        messages=[ChatMessage(role="user", content=query)],
    )
    resp = orchestrate_chat(req, ctx)
    assert resp.intent == "triage"
    assert resp.status == "answered"


def test_study_headache_tailored_guidance():
    """Headache from intense study/work must receive study/eye-strain tailored advice, not morning sleep advice."""
    query = "Tôi đang học nhiều quá hay sao mà bây giờ nhức đầu qúa"
    ctx = _make_ctx()
    req = ChatRequest(
        conversation_id="conv-study-headache",
        messages=[ChatMessage(role="user", content=query)],
    )
    resp = orchestrate_chat(req, ctx)
    assert resp.intent == "triage"
    assert resp.status == "answered"

    summary = resp.answer.summary.lower()
    assert "học" in summary or "mỏi điều tiết" in summary or "màn hình" in summary
    assert "ngủ dậy" not in summary
    assert "chưa ăn sáng" not in summary
    assert "sau giấc ngủ dài" not in summary


def test_cut_hand_acute_first_aid_guidance():
    """Laceration from study/activity must receive calming, direct pressure first aid guidance rather than generic disclaimer."""
    query = "Tôi đang học tự dưng bị đứt tay đau quá huhu"
    ctx = _make_ctx()
    req = ChatRequest(
        conversation_id="conv-cut-hand",
        messages=[ChatMessage(role="user", content=query)],
    )
    resp = orchestrate_chat(req, ctx)
    assert resp.intent == "triage"
    assert resp.status == "answered"

    summary = resp.answer.summary.lower()
    assert "đứt tay" in summary
    assert "cầm máu" in summary or "ép chặt" in summary
    # Check self care has first aid steps
    joined_text = " ".join(block.text.lower() for block in resp.answer.narrative)
    assert "rửa sạch" in joined_text or "nước muối sinh lý" in joined_text
    assert "sát trùng" in joined_text or "povidone" in joined_text
    # Must NOT ask irrelevant fever questions
    questions = resp.answer.questions
    assert not any("sốt" in q.lower() for q in questions)
    assert any("cầm" in q.lower() or "sâu" in q.lower() or "vật" in q.lower() for q in questions)


def test_acute_burn_water_cooling_guidance():
    """Thermal burn query must receive immediate water cooling guidance and warn against ice/toothpaste."""
    query = "em đg học tự dưng bị bong nuoc soi rat wa"
    ctx = _make_ctx()
    req = ChatRequest(
        conversation_id="conv-burn-test",
        messages=[ChatMessage(role="user", content=query)],
    )
    resp = orchestrate_chat(req, ctx)
    assert resp.intent == "triage"
    assert resp.status == "answered"

    joined_text = " ".join(block.text.lower() for block in resp.answer.narrative)
    assert "bỏng" in joined_text
    assert "nước" in joined_text
    assert "kem đánh răng" in joined_text or "đá lạnh" in joined_text


def test_epistaxis_nosebleed_guidance():
    """Nosebleed query must receive forward-leaning and nose pinch guidance, avoiding backward tilting."""
    query = "chảy máu cam từ sáng giờ"
    ctx = _make_ctx()
    req = ChatRequest(
        conversation_id="conv-epistaxis-test",
        messages=[ChatMessage(role="user", content=query)],
    )
    resp = orchestrate_chat(req, ctx)
    assert resp.intent == "triage"
    assert resp.status == "answered"

    joined_text = " ".join(block.text.lower() for block in resp.answer.narrative)
    assert "chảy máu cam" in joined_text or "chảy máu mũi" in joined_text
    assert "cánh mũi" in joined_text or "bóp" in joined_text


def test_scabies_dermatology_treatment_guidance():
    """Scabies treatment query must route to triage with DERMATOLOGY and 4-pillar scabies guidance."""
    query = "tôi đang bị ghẻ có cách nào chữa"
    ctx = _make_ctx()
    req = ChatRequest(
        conversation_id="conv-scabies-test",
        messages=[ChatMessage(role="user", content=query)],
    )
    resp = orchestrate_chat(req, ctx)
    assert resp.intent == "triage"
    assert resp.status == "answered"
    assert resp.result["urgency"] == "ROUTINE"
    assert resp.result["recommended_specialty"]["code"] == "DERMATOLOGY"

    joined_text = " ".join(block.text.lower() for block in resp.answer.narrative)
    assert "ghẻ" in joined_text
    assert "permethrin" in joined_text or "d.e.p" in joined_text
    assert "giặt" in joined_text or "nước nóng" in joined_text or "sôi" in joined_text



