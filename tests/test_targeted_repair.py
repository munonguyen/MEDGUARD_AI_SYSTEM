"""Unit Tests for Targeted Repair Engine (Phase 3.9)."""

from app.models.safety import ClinicalOutputGuardResult, SafetyKernelResult
from app.models.synthesis import FinalSynthesisResult
from app.services.clinical_intake_compiler import ClinicalIntakeCompiler
from app.services.clinical_output_guard import ClinicalOutputGuard
from app.services.targeted_repair import TargetedRepairEngine


def test_targeted_repair_fixes_unsupported_diagnosis_surgically():
    intake = ClinicalIntakeCompiler.compile("Tôi bị mỏi bắp chân")
    safety_kernel = SafetyKernelResult(emergency_lock=False, minimum_triage="ROUTINE")

    dogmatic_synth = FinalSynthesisResult(
        final_answer="Chào bạn, chắc chắn bạn bị huyết khối tĩnh mạch sâu cần đi mổ.",
        title="Tư vấn",
        summary="Nhận định",
        urgency="ROUTINE",
        specialty_code="ORTHOPEDICS",
        specialty_label="Cơ xương khớp",
        red_flags=["Sốt cao"],
    )

    guard_res = ClinicalOutputGuard.evaluate_output(intake, safety_kernel, dogmatic_synth)
    assert guard_res.safe is False

    repaired = TargetedRepairEngine.repair(
        intake=intake,
        safety_kernel=safety_kernel,
        synthesis=dogmatic_synth,
        guard_result=guard_res,
    )

    # Invariant: Dogmatic assertion replaced with cautious differential wording
    assert "chắc chắn bạn bị huyết khối tĩnh mạch sâu" not in repaired.final_answer.lower()
    assert "loại trừ nguy cơ huyết khối tĩnh mạch sâu" in repaired.final_answer.lower()

    # Re-evaluate with guard -> Should now pass!
    second_guard = ClinicalOutputGuard.evaluate_output(intake, safety_kernel, repaired)
    assert second_guard.safe is True


def test_targeted_repair_injects_115_on_emergency_lock():
    intake = ClinicalIntakeCompiler.compile("Đau thắt ngực lan tay trái")
    safety_kernel = SafetyKernelResult(emergency_lock=True, minimum_triage="EMERGENCY")

    impaired_synth = FinalSynthesisResult(
        final_answer="Bạn cần nghỉ ngơi và theo dõi.",
        title="Tư vấn",
        summary="Đau ngực",
        urgency="ROUTINE",
        specialty_code="CARDIOLOGY",
        specialty_label="Tim mạch",
    )

    guard_res = ClinicalOutputGuard.evaluate_output(intake, safety_kernel, impaired_synth)
    repaired = TargetedRepairEngine.repair(
        intake=intake,
        safety_kernel=safety_kernel,
        synthesis=impaired_synth,
        guard_result=guard_res,
    )

    assert repaired.urgency == "EMERGENCY"
    assert "115" in repaired.final_answer
    assert "đánh giá cấp cứu ngay" in repaired.final_answer.lower()
