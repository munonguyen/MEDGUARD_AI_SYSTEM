"""Unit tests for Multi-Judge Agent Evaluation Panel (Hội đồng Giám khảo)."""

from __future__ import annotations

import pytest

from app.services.jury_evaluator import (
    AgentJuryPanel,
    ClinicalDoctorJudge,
    DAGDecisionEvaluator,
    FactualGroundednessJudge,
    LegalComplianceJudge,
    PsychologicalEmpathyJudge,
    QAGEvaluator,
    ToolExecutionRecord,
    ToolLevelEvaluator,
    TrajectoryLevelEvaluator,
    TrajectoryStep,
)


def test_legal_compliance_judge_pass_and_veto():
    """Verify LegalComplianceJudge approves compliant answers and vetoes illegal diagnosis/prescriptions."""
    compliant_text = (
        "Theo thông tin Dược thư Quốc gia, Paracetamol cần thận trọng ở người suy gan. "
        "Bạn nên đi khám tại cơ sở y tế hoặc gặp bác sĩ chuyên khoa để được hướng dẫn."
    )
    verdict = LegalComplianceJudge.evaluate(compliant_text, abstains_from_diagnosis=True)
    assert verdict.passed is True
    assert verdict.veto_triggered is False
    assert 0.4 <= verdict.score <= 0.8

    # Illegal diagnosis & online prescription
    illegal_text = "Tôi chẩn đoán xác định bạn bị sốt xuất huyết. Tôi kê đơn cho bạn uống 2 viên thuốc kháng sinh mỗi ngày."
    bad_verdict = LegalComplianceJudge.evaluate(illegal_text, abstains_from_diagnosis=False)
    assert bad_verdict.passed is False
    assert bad_verdict.veto_triggered is True
    assert "VIOLATION_ILLEGAL_ONLINE_PRESCRIPTION_OR_DIAGNOSIS" in bad_verdict.violations


def test_psychological_empathy_judge():
    """Verify PsychologicalEmpathyJudge catches panic triggers and scores empathetic responses."""
    empathetic_text = (
        "Với thông tin hiện có, bạn nên theo dõi sát diễn biến và giữ bình tĩnh. "
        "Cho mình biết thêm triệu chứng xuất hiện từ khi nào?"
    )
    good_verdict = PsychologicalEmpathyJudge.evaluate(empathetic_text)
    assert good_verdict.passed is True
    assert 0.4 <= good_verdict.score <= 0.8

    panic_text = "Bạn có nguy cơ tử vong rất cao trong đêm nay nếu không uống thuốc!"
    bad_verdict = PsychologicalEmpathyJudge.evaluate(panic_text)
    assert bad_verdict.passed is False
    assert "PANIC_INDUCING_LANGUAGE" in bad_verdict.violations


def test_clinical_doctor_judge():
    """Verify ClinicalDoctorJudge enforces locked safety claims and triage escalation."""
    locked_claim = "Chống chỉ định dùng Metformin khi eGFR < 30 mL/phút"
    valid_text = f"Thông tin y khoa xác định: {locked_claim}. Cần tư vấn bác sĩ điều trị."

    good_verdict = ClinicalDoctorJudge.evaluate(
        valid_text,
        locked_claims=[locked_claim],
        specialty_label="Nội tiết",
        red_flags_present=False,
    )
    assert good_verdict.passed is True

    # Omitted locked claim
    bad_text = "Bệnh nhân có thể dùng thuốc này bình thường mà không cần kiểm tra thận."
    bad_verdict = ClinicalDoctorJudge.evaluate(
        bad_text,
        locked_claims=[locked_claim],
        specialty_label="Nội tiết",
        red_flags_present=False,
    )
    assert bad_verdict.passed is False
    assert "MISSING_LOCKED_SAFETY_CLAIM" in bad_verdict.violations


def test_qag_atomization_and_groundedness():
    """Verify QAG decomposes text into claims and checks against evidence contexts."""
    text = "Sildenafil tương tác nguy hiểm với nitroglycerin. Bệnh nhân có thể bị tụt huyết áp nghiêm trọng."
    claims = QAGEvaluator.atomize_claims(text)
    assert len(claims) >= 2

    contexts = ["Sildenafil phối hợp nitroglycerin gây tụt huyết áp tư thế nghiêm trọng, giãn mạch vành."]
    res = QAGEvaluator.evaluate_groundedness(text, contexts)
    assert res["total_claims"] >= 2
    assert res["supported_claims"] >= 1
    assert 0.3 <= res["groundedness_ratio"] <= 0.8


def test_dag_decision_tree_evaluator():
    """Verify DAG metric detects missing emergency escalation when red flags are present."""
    # Emergency without hospital advice -> violation
    bad_dag = DAGDecisionEvaluator.evaluate_logic_tree(
        user_intent="triage",
        triage_urgency="EMERGENCY",
        red_flags_present=True,
        response_text="Bạn cứ ở nhà nghỉ ngơi uống nước nhiều sẽ đỡ.",
    )
    assert bad_dag["passed"] is False
    assert "DAG_MISSING_EMERGENCY_ESCALATION" in bad_dag["violations"]

    # Emergency with 115 call -> pass
    good_dag = DAGDecisionEvaluator.evaluate_logic_tree(
        user_intent="triage",
        triage_urgency="EMERGENCY",
        red_flags_present=True,
        response_text="Gọi ngay 115 hoặc đến cơ sở cấp cứu bệnh viện gần nhất lập tức!",
    )
    assert good_dag["passed"] is True


def test_tool_and_trajectory_evaluators():
    """Verify Tool-level and Trajectory-level metrics compute proper centered scores."""
    tool_records = [
        ToolExecutionRecord(
            tool_name="knowledge_retriever",
            parameters={"query": "aspirin"},
            expected_tool="knowledge_retriever",
            expected_parameters={"query": "aspirin"},
            execution_order=1,
        )
    ]
    tool_metrics = ToolLevelEvaluator.evaluate(tool_records)
    assert "ToolSelectionAccuracy" in tool_metrics
    assert "ToolParameterAccuracy" in tool_metrics
    assert 0.3 <= tool_metrics["ToolSelectionAccuracy"] <= 0.8

    trajectory = [
        TrajectoryStep(node_name="researcher", action="fetch", reasoning="context"),
        TrajectoryStep(node_name="writer", action="write", reasoning="draft"),
        TrajectoryStep(node_name="reviewer", action="review", reasoning="safety"),
    ]
    traj_metrics = TrajectoryLevelEvaluator.evaluate(trajectory)
    assert "StepEfficiency" in traj_metrics
    assert "PlanAdherence" in traj_metrics
    assert 0.3 <= traj_metrics["PlanAdherence"] <= 0.8


def test_full_jury_panel_consensus_and_framework_exports():
    """Verify master AgentJuryPanel integrates all judges and exports DeepEval/Langfuse schemas."""
    panel = AgentJuryPanel()
    answer = (
        "Với thông tin hiện có, cần thận trọng tương tác giữa Clarithromycin và Simvastatin. "
        "Bạn nên giữ bình tĩnh và trao đổi với bác sĩ chuyên khoa để được tư vấn thay đổi liều an toàn."
    )
    contexts = ["Clarithromycin ức chế CYP3A4 làm tăng nồng độ Simvastatin trong máu gây nguy cơ tổn thương cơ."]

    scorecard = panel.evaluate(
        evaluation_id="EVAL-TEST-001",
        answer_text=answer,
        contexts=contexts,
        locked_claims=["tương tác giữa Clarithromycin và Simvastatin"],
        abstains_from_diagnosis=True,
        red_flags_present=False,
    )

    assert scorecard.overall_passed is True
    assert scorecard.veto_active is False
    assert len(scorecard.verdicts) == 4
    assert 0.3 <= scorecard.consensus_score <= 0.8

    # DeepEval export check
    deepeval_data = scorecard.export_deepeval()
    assert deepeval_data["test_case_id"] == "EVAL-TEST-001"
    assert len(deepeval_data["metrics_data"]) == 4

    # Langfuse export check
    langfuse_data = scorecard.export_langfuse()
    assert len(langfuse_data) == 4
    for item in langfuse_data:
        assert "name" in item
        assert "value" in item
        assert item["data_type"] == "NUMERIC"
