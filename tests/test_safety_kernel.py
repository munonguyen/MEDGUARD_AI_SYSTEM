"""Unit Tests for Safety Kernel (Phase 3.1 & Phase 3.15)."""

from app.models.intake import CompiledClinicalIntake
from app.services.clinical_intake_compiler import ClinicalIntakeCompiler
from app.services.safety_kernel import SafetyKernel


def test_safety_kernel_detects_stroke_fast_positive():
    intake = ClinicalIntakeCompiler.compile("Bác tôi đột nhiên bị méo miệng và yếu liệt nửa người bên trái")
    kernel_res = SafetyKernel.evaluate(intake)

    assert kernel_res.emergency_lock is True
    assert kernel_res.minimum_triage == "EMERGENCY"
    assert any("STROKE" in r for r in kernel_res.triggered_rules)
    assert any("115" in act for act in kernel_res.mandatory_actions)


def test_safety_kernel_detects_cardiac_acs_pattern():
    intake = ClinicalIntakeCompiler.compile("Tôi bị đau thắt ngực đè nặng lan tay trái kèm khó thở và vã mồ hôi")
    kernel_res = SafetyKernel.evaluate(intake)

    assert kernel_res.emergency_lock is True
    assert kernel_res.minimum_triage == "EMERGENCY"
    assert any("ACS" in r for r in kernel_res.triggered_rules)


def test_safety_kernel_detects_thunderclap_headache():
    intake = ClinicalIntakeCompiler.compile("Tôi bị đau đầu dữ dội như sét đánh, chưa từng đau như vậy trong đời")
    kernel_res = SafetyKernel.evaluate(intake)

    assert kernel_res.emergency_lock is True
    assert kernel_res.minimum_triage == "EMERGENCY"
    assert any("THUNDERCLAP" in r for r in kernel_res.triggered_rules)


def test_safety_kernel_permits_benign_routine_cases():
    intake = ClinicalIntakeCompiler.compile("Tôi bị mỏi bắp chân sau khi đi bộ 5km, không sưng không đỏ")
    kernel_res = SafetyKernel.evaluate(intake)

    assert kernel_res.emergency_lock is False
    assert kernel_res.minimum_triage == "ROUTINE"
    assert kernel_res.disposition == "SAFE_ROUTINE"
    assert len(kernel_res.hard_red_flags) == 0


def test_safety_kernel_blocks_aspirin_on_bleeding_risk():
    intake = ClinicalIntakeCompiler.compile("Tôi đang nghi sốt xuất huyết chảy máu chân răng, có uống aspirin được không?")
    kernel_res = SafetyKernel.evaluate(intake)

    assert any("ASPIRIN" in r for r in kernel_res.triggered_rules)
    assert len(kernel_res.medication_hard_blocks) > 0
    assert "CHỐNG CHỈ ĐỊNH" in kernel_res.medication_hard_blocks[0]
