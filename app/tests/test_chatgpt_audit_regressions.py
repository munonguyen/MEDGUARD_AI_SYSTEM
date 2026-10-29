"""Comprehensive regression test suite for ChatGPT clinical audit.

Validates the 12 architectural and clinical invariants:
1. Emergency Override (Veto): Suppression of self-care, home monitoring, and benign differentials.
2. Thunderclap headache recognition (< 1 min, 10/10, exertion/gym/sex).
3. Pain improvement non-downgrade (symptom_improved_after_onset != safe).
4. Non-Exclusion Rules: Absence of vomiting != absence of intracranial bleed; can flex neck != absence of meningitis.
5. Exact evidence extraction without unconfirmed hallucinated symptoms.
6. ASK_ONLY_IF_UNKNOWN: Filtering questions for symptoms user already affirmed/denied.
7. Post-generation Response Validator: Stripping forbidden reassurance in emergencies.
"""

from __future__ import annotations

import pytest

from app.core.context import RequestContext
from app.models.chat import ChatContext, ChatMessage, ChatRequest
from app.models.triage import TriageRequest
from app.services.chat import _extract_vital_signs, orchestrate_chat
from app.services.clinical_text import (
    extract_clinical_facts,
    filter_known_clarifying_questions,
    NON_EXCLUSION_RULES,
)
from app.services.rules import triage_rules
from app.services.triage import evaluate_triage


@pytest.fixture
def ctx() -> RequestContext:
    return RequestContext(
        request_id="test-chatgpt-audit",
        tenant_id="tenant-audit",
        idempotency_key="key-audit",
    )


def test_case_1_thunderclap_headache_gym_emergency_override(ctx: RequestContext) -> None:
    """Case 1: 10/10 in < 1 min during gym must map to EMERGENCY and veto all self-care."""
    text = "đau đầu đột ngột khi đang tập gym 10/10 đạt đỉnh trong chưa đầy 1 phút"
    vitals = _extract_vital_signs(text)
    rule_res = triage_rules(text, vitals)

    assert rule_res.urgency == "EMERGENCY"
    assert rule_res.esi_level in (1, 2)
    assert rule_res.emergency_flag is True

    # End-to-end chat response validation
    chat_req = ChatRequest(
        conversation_id="conv-audit-c1",
        messages=[ChatMessage(role="user", content=text)],
        context=ChatContext(),
    )
    chat_res = orchestrate_chat(chat_req, ctx)
    assert chat_res.answer is not None
    assert chat_res.answer.title == "Gọi 115 hoặc đến khoa Cấp cứu ngay"
    assert chat_res.answer.clinical_hypotheses == []
    assert chat_res.answer.questions == []

    narrative_text = " ".join(b.text for b in chat_res.answer.narrative).lower()

    # Must contain emergency action
    assert "115" in narrative_text or "cấp cứu" in narrative_text

    # Forbidden reassuring and self-care phrases MUST NOT appear
    forbidden = [
        "chưa thấy dấu hiệu cấp cứu",
        "chưa cho thấy rõ dấu hiệu",
        "căng thẳng",
        "thiếu ngủ",
        "mỏi mắt",
        "chườm mát",
        "nghỉ ngơi",
        "theo dõi 1-2 ngày",
        "theo dõi thêm",
    ]
    for phrase in forbidden:
        assert phrase not in narrative_text, f"Forbidden phrase '{phrase}' found in emergency narrative!"


def test_case_2_isolated_severe_headache_no_hallucinated_onset(ctx: RequestContext) -> None:
    """Case 2: Severe headache without sudden onset should be URGENT (ESI 3)
    and must NOT hallucinate 'khởi phát đột ngột'. Negative 'không yếu liệt' must not exclude.
    """
    text = "Tôi bị đau đầu dữ dội nhưng không yếu liệt"
    facts = extract_clinical_facts(text)
    assert "khong yeu liet" in facts.negative_findings
    assert facts.sudden_onset is False

    vitals = _extract_vital_signs(text)
    rule_res = triage_rules(text, vitals)

    assert rule_res.urgency == "URGENT"
    assert rule_res.esi_level == 3
    assert rule_res.emergency_flag is False

    # Evidence label must NOT claim sudden onset
    for rf in rule_res.red_flags:
        assert "đột ngột" not in rf, f"Hallucinated 'đột ngột' in red flags: {rf}"

    # End-to-end chat turn
    chat_req = ChatRequest(
        conversation_id="conv-audit-c2",
        messages=[ChatMessage(role="user", content=text)],
        context=ChatContext(),
    )
    chat_res = orchestrate_chat(chat_req, ctx)
    assert chat_res.answer is not None
    assert chat_res.answer.title == "Bạn nên được nhân viên y tế đánh giá sớm"

    # ASK_ONLY_IF_UNKNOWN: questions must not ask if patient has weakness since user already said 'không yếu liệt'
    for q in chat_res.answer.questions:
        assert "yếu hoặc tê" not in q.lower() and "yếu liệt" not in q.lower()


def test_case_3_post_coital_sudden_headache_emergency(ctx: RequestContext) -> None:
    """Case 3: Sudden headache after sex -> EMERGENCY without hallucinating severity words."""
    text = "đau đầu sau quan hệ xuất hiện rất đột ngột chưa từng bị"
    vitals = _extract_vital_signs(text)
    rule_res = triage_rules(text, vitals)

    assert rule_res.urgency == "EMERGENCY"
    assert rule_res.esi_level == 2
    assert rule_res.emergency_flag is True

    chat_req = ChatRequest(
        conversation_id="conv-audit-c3",
        messages=[ChatMessage(role="user", content=text)],
        context=ChatContext(),
    )
    chat_res = orchestrate_chat(chat_req, ctx)
    assert chat_res.answer is not None
    assert chat_res.answer.title == "Gọi 115 hoặc đến khoa Cấp cứu ngay"


def test_case_4_meningitis_combination_non_exclusion(ctx: RequestContext) -> None:
    """Case 4: Headache + fever 38.5 + neck stiffness ('vẫn cúi được' does NOT exclude).
    Must NOT emit generic 'sinh hiệu cần được đánh giá sớm'.
    """
    text = "đau đầu sốt 38.5°C buồn nôn cổ hơi cứng nhưng tôi vẫn cúi được"
    facts = extract_clinical_facts(text)
    assert "van cui duoc" in facts.negative_findings

    vitals = _extract_vital_signs(text)
    rule_res = triage_rules(text, vitals)

    assert rule_res.urgency == "EMERGENCY"
    assert rule_res.esi_level == 2
    assert rule_res.emergency_flag is True

    # Red flags must specify meningitis risk and not use generic 'sinh hiệu'
    red_flag_str = " ".join(rule_res.red_flags)
    assert "màng não" in red_flag_str or "nhiễm trùng" in red_flag_str
    assert "sinh hiệu cần được đánh giá sớm" not in red_flag_str

    chat_req = ChatRequest(
        conversation_id="conv-audit-c4",
        messages=[ChatMessage(role="user", content=text)],
        context=ChatContext(),
    )
    chat_res = orchestrate_chat(chat_req, ctx)
    assert chat_res.answer is not None
    assert chat_res.answer.title == "Gọi 115 hoặc đến khoa Cấp cứu ngay"


def test_case_5_head_trauma_drowsiness_non_exclusion(ctx: RequestContext) -> None:
    """Case 5: Head injury yesterday + drowsiness today ('không nôn' does NOT exclude).
    Must NOT emit generic 'sinh hiệu'.
    """
    text = "ngã xe hôm qua đau đầu hôm nay buồn ngủ hơn bình thường không nôn"
    facts = extract_clinical_facts(text)
    assert "khong non" in facts.negative_findings

    vitals = _extract_vital_signs(text)
    rule_res = triage_rules(text, vitals)

    assert rule_res.urgency == "EMERGENCY"
    assert rule_res.esi_level == 2
    assert rule_res.emergency_flag is True

    red_flag_str = " ".join(rule_res.red_flags)
    assert "chấn thương" in red_flag_str or "buồn ngủ" in red_flag_str
    assert "sinh hiệu" not in red_flag_str

    chat_req = ChatRequest(
        conversation_id="conv-audit-c5",
        messages=[ChatMessage(role="user", content=text)],
        context=ChatContext(),
    )
    chat_res = orchestrate_chat(chat_req, ctx)
    assert chat_res.answer is not None
    assert chat_res.answer.title == "Gọi 115 hoặc đến khoa Cấp cứu ngay"


def test_case_6_thunderclap_pain_improved_non_downgrade(ctx: RequestContext) -> None:
    """Case 6: Pain improved after onset (10/10 down to 6/10) must NOT downgrade EMERGENCY."""
    text = "đau đầu sét đánh đạt đỉnh trong chưa đầy 1 phút nhưng giờ đã đỡ từ 10/10 xuống 6/10"
    facts = extract_clinical_facts(text)
    assert facts.improved_after_onset is True
    assert facts.severity_score == 10
    assert facts.time_to_peak_seconds == 60

    vitals = _extract_vital_signs(text)
    rule_res = triage_rules(text, vitals)

    assert rule_res.urgency == "EMERGENCY"
    assert rule_res.esi_level == 2
    assert rule_res.emergency_flag is True


def test_case_7_chest_pain_dyspnea_emergency(ctx: RequestContext) -> None:
    """Case 7: Chest pain with radiation and cold sweat -> EMERGENCY."""
    text = "đau thắt ngực lan lên hàm và vã mồ hôi lạnh khó thở"
    rule_res = triage_rules(text, None)
    assert rule_res.urgency == "EMERGENCY"
    assert rule_res.esi_level == 2


def test_case_8_stroke_fast_emergency(ctx: RequestContext) -> None:
    """Case 8: Sudden facial droop and speech difficulty -> EMERGENCY (Stroke golden window)."""
    text = "bác tôi bị méo miệng và nói ngọng đột ngột"
    rule_res = triage_rules(text, None)
    assert rule_res.urgency == "EMERGENCY"
    assert rule_res.esi_level == 2


def test_case_9_anticoagulant_head_trauma(ctx: RequestContext) -> None:
    """Case 9: Patient on anticoagulant with head trauma is high risk."""
    text = "tôi đang uống warfarin bị ngã đập đầu"
    facts = extract_clinical_facts(text)
    assert "head_trauma" in facts.triggers
    rule_res = triage_rules(text, None)
    assert rule_res.urgency == "EMERGENCY"
    assert rule_res.esi_level == 2
    assert rule_res.emergency_flag is True


def test_ask_only_if_unknown_filter() -> None:
    """Test ASK_ONLY_IF_UNKNOWN removes questions already answered in the query."""
    text = "đau đầu 10/10 xuất hiện đột ngột không nôn không yếu liệt"
    facts = extract_clinical_facts(text)
    assert facts.severity_score == 10
    assert facts.sudden_onset is True
    assert "khong non" in facts.negative_findings
    assert "khong yeu liet" in facts.negative_findings

    questions = [
        "Đau ở vị trí nào, mức độ từ 0 đến 10 và bắt đầu từ lúc nào?",
        "Cơn đau có xuất hiện đột ngột và đạt mức dữ dội nhất trong vài phút không?",
        "Có yếu hoặc tê một bên không?",
        "Có nôn liên tục không?",
        "Bạn có tiền sử dị ứng thuốc không?",
    ]
    filtered = filter_known_clarifying_questions(questions, facts)

    # 0 den 10, xuat hien dot ngot, yeu hoac te, co non should be filtered out
    assert len(filtered) == 1
    assert "dị ứng thuốc" in filtered[0]
