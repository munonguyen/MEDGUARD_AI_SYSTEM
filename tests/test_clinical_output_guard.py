"""Unit Tests for Clinical Output Guard (Phase 3.7)."""

from app.models.safety import SafetyKernelResult
from app.models.synthesis import FinalSynthesisResult
from app.services.clinical_intake_compiler import ClinicalIntakeCompiler
from app.services.clinical_output_guard import ClinicalOutputGuard


def test_output_guard_passes_safe_response():
    intake = ClinicalIntakeCompiler.compile("Tôi bị mỏi bắp chân")
    safety_kernel = SafetyKernelResult(emergency_lock=False, minimum_triage="ROUTINE")

    safe_synth = FinalSynthesisResult(
        final_answer="Bạn bị mỏi cơ sau vận động. Hãy nghỉ ngơi, chườm ấm và theo dõi tại nhà.",
        title="Tư vấn Cơ xương khớp",
        summary="Mỏi cơ cơ học",
        urgency="ROUTINE",
        specialty_code="ORTHOPEDICS",
        specialty_label="Cơ xương khớp",
        red_flags=["Bắp chân sưng to nóng đỏ"],
    )

    guard_res = ClinicalOutputGuard.evaluate_output(intake, safety_kernel, safe_synth)
    assert guard_res.safe is True
    assert guard_res.action == "PASS"


def test_output_guard_vetoes_emergency_downgrade_and_missing_115():
    intake = ClinicalIntakeCompiler.compile("Đau ngực dữ dội lan tay trái")
    safety_kernel = SafetyKernelResult(emergency_lock=True, minimum_triage="EMERGENCY")

    downgraded_synth = FinalSynthesisResult(
        final_answer="Bạn chỉ cần nghỉ ngơi uống nước.",  # Missing 115 and downgraded!
        title="Tư vấn",
        summary="Đau ngực",
        urgency="ROUTINE",  # Downgraded!
        specialty_code="CARDIOLOGY",
        specialty_label="Tim mạch",
        red_flags=[],
    )

    guard_res = ClinicalOutputGuard.evaluate_output(intake, safety_kernel, downgraded_synth)
    assert guard_res.safe is False
    assert guard_res.action == "SAFE_FALLBACK"
    assert any(v["code"] == "EMERGENCY_DOWNGRADE" for v in guard_res.violations)
    assert any(v["code"] == "MISSING_EMERGENCY_ACTION" for v in guard_res.violations)


def test_output_guard_detects_unsupported_definitive_diagnosis():
    intake = ClinicalIntakeCompiler.compile("Tôi bị mỏi chân")
    safety_kernel = SafetyKernelResult(emergency_lock=False, minimum_triage="ROUTINE")

    dogmatic_synth = FinalSynthesisResult(
        final_answer="Chắc chắn bạn bị huyết khối tĩnh mạch sâu cần phẫu thuật.",
        title="Tư vấn",
        summary="Chẩn đoán",
        urgency="ROUTINE",
        specialty_code="ORTHOPEDICS",
        specialty_label="Cơ xương khớp",
        red_flags=["Sốt cao"],
    )

    guard_res = ClinicalOutputGuard.evaluate_output(intake, safety_kernel, dogmatic_synth)
    assert guard_res.safe is False
    assert guard_res.action == "REPAIR"
    assert any(v["code"] == "UNSUPPORTED_DIAGNOSIS" for v in guard_res.violations)
