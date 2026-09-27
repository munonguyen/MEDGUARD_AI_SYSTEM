"""Integration Tests for Phase 3 Master Clinical Pipeline."""

from app.services.phase3_pipeline import Phase3ClinicalPipeline


def test_phase3_pipeline_benign_calf_fatigue_end_to_end():
    query = (
        "Chào bác sĩ, em 24t, 2 ngày nay sau khi đi bộ nhiều thì bắp chân trái bị căng mỏi ê ẩm, "
        "nhưng ko sưng, ko đỏ, đi lại bình thường. Em đọc mạng sợ bị cục máu đông quá, mong bs tư vấn."
    )
    result = Phase3ClinicalPipeline.execute(query)

    # 1. Output Safety & Verification
    assert result.output_guard.safe is True
    assert result.evidence_verification.verified is True
    assert result.final_synthesis.urgency == "ROUTINE"
    assert result.final_synthesis.specialty_code == "ORTHOPEDICS"

    # 2. Invariant: Patient anxiety isolated from diagnosis
    assert not any("huyết khối" in f for f in result.intake.clinical_form.positive_findings)
    assert any("cục máu đông" in c.stated_concern.lower() for c in result.intake.patient_concerns)
    assert "chắc chắn bị" not in result.final_synthesis.final_answer.lower()

    # 3. Invariant: Critic and Jev operated atomically
    assert result.critic_report.critic_pass is True
    assert result.jev_judgment.overtriage_probability < 0.50
    assert result.arbitration.action == "ACCEPT_A"
    assert result.pipeline_latency_ms < 5000.0  # Well within 60s budget!


def test_phase3_pipeline_emergency_cardiac_fast_lane_end_to_end():
    query = "Tôi bị đau thắt ngực đè nặng dữ dội lan lên hàm và tay trái kèm vã mồ hôi lạnh và khó thở."
    result = Phase3ClinicalPipeline.execute(query)

    # 1. Safety Kernel Emergency Lock Active
    assert result.safety_kernel.emergency_lock is True
    assert result.final_synthesis.urgency == "EMERGENCY"

    # 2. Output Guard & 115 directive
    assert "115" in result.final_synthesis.final_answer
    assert result.output_guard.safe is True
    assert any("ACS" in r for r in result.safety_kernel.triggered_rules)
