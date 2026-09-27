"""Tests for Multi-Gateway Candidate Evaluator & Medical Jury Gateway."""

import pytest

from app.models.agents import AgentEvidenceSource
from app.services.clinical_llm_synthesizer import ClinicalSynthesisResult
from app.services.multi_gateway_jury import (
    GatewayCandidate,
    GatewayQualityEvaluator,
    evaluate_and_certify_gateway_response,
)


def test_gateway_quality_evaluator_safety_penalty_on_emergency_downgrade():
    """Verify that any candidate attempting to downgrade an EMERGENCY is heavily penalized."""
    candidate = GatewayCandidate(
        gateway_name="gemini_clinical_gateway",
        urgency="ROUTINE",  # Attempted downgrade
        specialty_code="CARDIOLOGY",
        specialty_label="Tim mạch",
        title="Theo dõi tại nhà",
        summary="Triệu chứng không nguy hiểm",
        reply="Bạn chỉ cần nghỉ ngơi theo dõi tại nhà.",
    )

    score = GatewayQualityEvaluator.evaluate_candidate(
        candidate,
        query="tôi bị đau ngực lan tay trái",
        deterministic_urgency="EMERGENCY",
    )

    assert candidate.quality_scores["safety"] == 0.0
    assert score <= 0.45
    assert any("VIOLATION" in note for note in candidate.evaluation_notes)


def test_gateway_quality_evaluator_rewards_authoritative_sources():
    """Verify that candidate with verified government/WHO medical guidelines scores higher."""
    sources = [
        AgentEvidenceSource(
            source_id="src_byt_ent",
            title="Hướng dẫn chẩn đoán và điều trị bệnh Tai Mũi Họng (Quyết định 3982/QĐ-BYT)",
            publisher="Bộ Y Tế Việt Nam",
            url="https://kcb.vn/van-ban/quyet-dinh-3982.html",
            authority_tier="government_health",
            supports_claim_ids=["c_diag", "c_care"],
        ),
        AgentEvidenceSource(
            source_id="src_who_rhinitis",
            title="WHO Guidelines on Rhinitis and Acute Respiratory Infections",
            publisher="Tổ chức Y tế Thế giới (WHO)",
            url="https://www.who.int/publications/i/item/9789241549691",
            authority_tier="guideline_or_regulator",
            supports_claim_ids=["c_diag"],
        ),
    ]

    candidate = GatewayCandidate(
        gateway_name="gemini_clinical_gateway",
        urgency="ROUTINE",
        specialty_code="ENT",
        specialty_label="Tai Mũi Họng",
        title="Tư vấn lâm sàng Tai Mũi Họng",
        summary="Cảm lạnh hoặc viêm mũi dị ứng",
        reply="Chào bạn, tình trạng sổ mũi của bạn có thể là cảm lạnh thông thường hoặc viêm mũi dị ứng. Bạn nên rửa mũi nước muối sinh lý ấm và nghỉ ngơi.",
        narrative_blocks=[
            {"kind": "paragraph", "text": "Đánh giá triệu chứng sổ mũi", "emphasis": [], "source_ids": ["src_byt_ent"]},
            {"kind": "paragraph", "text": "Hướng dẫn chăm sóc an toàn", "emphasis": [], "source_ids": ["src_who_rhinitis"]},
        ],
        sources=sources,
        self_care=["Rửa mũi bằng nước muối 0.9%", "Uống nước ấm"],
        red_flags=["Sốt cao > 38.5 kéo dài"],
    )

    score = GatewayQualityEvaluator.evaluate_candidate(
        candidate,
        query="tôi đang rất sổ mũi",
        deterministic_urgency="ROUTINE",
    )

    assert candidate.quality_scores["grounding"] >= 0.90
    assert candidate.quality_scores["safety"] == 1.0
    assert score >= 0.85


def test_evaluate_and_certify_gateway_response_approves_safe_candidate():
    """Verify end-to-end evaluation: Candidate with sources evaluated and certified by Medical Jury."""
    synth = ClinicalSynthesisResult(
        urgency="ROUTINE",
        specialty_code="ENT",
        specialty_label="Tai Mũi Họng",
        title="Tư vấn Tai Mũi Họng từ MedGuard AI",
        summary="Triệu chứng viêm đường hô hấp trên thông thường",
        reply=(
            "Chào bạn, tình trạng sổ mũi nhiều có thể do cảm lạnh thông thường hoặc viêm mũi dị ứng.\n\n"
            "Bạn hãy giữ ấm cơ thể, vệ sinh mũi bằng dung dịch nước muối sinh lý 0.9% và uống nhiều nước ấm. "
            "Nếu xuất hiện sốt cao kéo dài hoặc khó thở, bạn hãy đến cơ sở y tế để được bác sĩ thăm khám."
        ),
        narrative_blocks=[
            {
                "kind": "paragraph",
                "text": "Tình trạng sổ mũi nhiều có thể do cảm lạnh thông thường hoặc viêm mũi dị ứng.",
                "emphasis": ["sổ mũi nhiều"],
                "source_ids": ["src_byt_ent_3982"],
            },
            {
                "kind": "paragraph",
                "text": "Bạn hãy giữ ấm cơ thể, vệ sinh mũi bằng dung dịch nước muối sinh lý 0.9% và uống nhiều nước ấm.",
                "emphasis": ["nước muối sinh lý 0.9%"],
                "source_ids": ["src_who_rhinitis"],
            },
        ],
        sources=[
            {
                "source_id": "src_byt_ent_3982",
                "title": "Hướng dẫn chẩn đoán và điều trị một số bệnh về Tai Mũi Họng (Quyết định 3982/QĐ-BYT)",
                "publisher": "Bộ Y Tế Việt Nam",
                "url": "https://kcb.vn/van-ban/quyet-dinh-so-3982-qd-byt-ve-viec-ban-hanh-tai-lieu-chuyen-mon-huong-dan-chan-doan-va-dieu-tri-mot-so-benh-ve-tai-mui-hong.html",
                "authority_tier": "government_health",
                "supports_claim_ids": ["c_diag", "c_care"],
            },
            {
                "source_id": "src_who_rhinitis",
                "title": "WHO Clinical Practice: Prevention and Management of Acute Respiratory Infections",
                "publisher": "Tổ chức Y tế Thế giới (WHO)",
                "url": "https://www.who.int/publications/i/item/9789241549691",
                "authority_tier": "guideline_or_regulator",
                "supports_claim_ids": ["c_care"],
            },
        ],
        red_flags=["Sốt cao trên 38.5 độ C kéo dài", "Khó thở"],
        clarifying_questions=["Dịch mũi của bạn trong hay đục vàng?"],
        self_care=["Vệ sinh mũi bằng dung dịch nước muối sinh lý 0.9%", "Uống nhiều nước ấm và giữ ấm cơ thể"],
    )

    result = evaluate_and_certify_gateway_response(
        query="tôi đang rất sổ mũi",
        gemini_synth=synth,
        rule_result={"urgency": "ROUTINE", "recommended_specialty": {"code": "ENT", "label": "Tai Mũi Họng"}},
        rule_reply="Phân luồng: Tai Mũi Họng",
        request_id="REQ-TEST-1234",
    )

    assert result.approved is True
    assert result.status == "verified"
    assert result.winning_gateway == "gemini_clinical_gateway"
    assert result.verification_scores is not None
    assert result.verification_scores.safety >= 0.95
    assert result.verification_scores.grounding >= 0.90
    assert len(result.candidate.sources) >= 1
    assert result.scorecard is not None
    assert result.scorecard.overall_passed is True


def test_gateway_quality_evaluator_rewards_jev_self_care_alignment():
    """Verify Jev reinforces candidate with calm self-care instructions on routine cases."""
    from app.models.jev import JevDecision

    jev_routine = JevDecision(
        action="SELF_CARE",
        confidence=0.96,
        allow_home_monitoring=True,
        require_human_review=False,
        triage_recommendation="ROUTINE",
        policy_rules_triggered=("benign_routine_self_care",),
    )

    calm_candidate = GatewayCandidate(
        gateway_name="gemini_clinical_gateway",
        urgency="ROUTINE",
        specialty_code="ORTHOPEDICS",
        specialty_label="Cơ xương khớp",
        title="Tư vấn đau mỏi cơ",
        summary="Căng cơ nhẹ, đáp ứng tốt với nghỉ ngơi",
        reply="Chào bạn, bạn nên nghỉ ngơi, chườm ấm thư giãn cơ và uống đủ nước theo dõi tại nhà.",
        self_care=["Nghỉ ngơi kê cao chân", "Chườm ấm", "Uống nước điện giải"],
        red_flags=["Sưng to nóng đỏ bắp chân"],
    )

    over_triaged_candidate = GatewayCandidate(
        gateway_name="deterministic_rule_gateway",
        urgency="URGENT",  # Over-triage on a benign case
        specialty_code="ORTHOPEDICS",
        specialty_label="Cơ xương khớp",
        title="Cảnh báo cần khám ngay",
        summary="Cần đến bệnh viện cấp cứu gấp",
        reply="Bạn phải đến bệnh viện khám ngay trong hôm nay vì nguy cơ cao.",
        self_care=[],
    )

    score_calm = GatewayQualityEvaluator.evaluate_candidate(
        calm_candidate,
        query="tôi bị mỏi cơ chân sau khi đi bộ",
        deterministic_urgency="ROUTINE",
        jev_decision=jev_routine,
    )

    score_over = GatewayQualityEvaluator.evaluate_candidate(
        over_triaged_candidate,
        query="tôi bị mỏi cơ chân sau khi đi bộ",
        deterministic_urgency="ROUTINE",
        jev_decision=jev_routine,
    )

    assert score_calm > score_over
    assert calm_candidate.quality_scores["jev_alignment"] >= 0.90
    assert over_triaged_candidate.quality_scores["jev_alignment"] <= 0.60
    assert any("Rewarded for calm" in note for note in calm_candidate.evaluation_notes)
    assert any("Jev Penalty: Over-triage" in note for note in over_triaged_candidate.evaluation_notes)


def test_gateway_quality_evaluator_penalizes_ignoring_jev_emergency():
    """Verify that if Jev mandates emergency, a candidate ignoring it gets heavily penalized."""
    from app.models.jev import JevDecision

    jev_emergency = JevDecision(
        action="EMERGENCY_NOW",
        confidence=0.99,
        allow_home_monitoring=False,
        require_human_review=False,
        triage_recommendation="EMERGENCY",
        policy_rules_triggered=("emergency_cardiac_floor_locked",),
    )

    under_triaged_candidate = GatewayCandidate(
        gateway_name="gemini_clinical_gateway",
        urgency="ROUTINE",
        specialty_code="CARDIOLOGY",
        specialty_label="Tim mạch",
        title="Tư vấn tim mạch",
        summary="Cảm giác khó chịu ngực",
        reply="Bạn có thể nghỉ ngơi uống nước.",
    )

    score = GatewayQualityEvaluator.evaluate_candidate(
        under_triaged_candidate,
        query="đau thắt ngực dữ dội đè nặng vã mồ hôi",
        deterministic_urgency="ROUTINE",
        jev_decision=jev_emergency,
    )

    assert score <= 0.50
    assert under_triaged_candidate.quality_scores["jev_alignment"] == 0.10
    assert any("Jev VIOLATION" in note for note in under_triaged_candidate.evaluation_notes)


def test_evaluate_and_certify_preserves_jev_decision_in_result():
    """Verify that JevDecision is captured in JuryEvaluationResult."""
    from app.models.jev import JevDecision

    jev_decision = JevDecision(
        action="SELF_CARE",
        confidence=0.95,
        allow_home_monitoring=True,
        require_human_review=False,
        triage_recommendation="ROUTINE",
    )

    result = evaluate_and_certify_gateway_response(
        query="tôi bị mỏi cơ chân",
        gemini_synth=None,
        rule_result={"urgency": "ROUTINE", "recommended_specialty": {"code": "ORTHOPEDICS", "label": "Cơ xương khớp"}},
        rule_reply="Bạn hãy nghỉ ngơi và theo dõi tại nhà.",
        jev_decision=jev_decision,
    )

    assert result.jev_decision is not None
    assert result.jev_decision.action == "SELF_CARE"

