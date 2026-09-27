"""Clinical Output Guard for MedGuard AI System.

Phase 3.7 Architecture Invariant:
1. Complete Separation from Generation: Independent release authority downstream of
   Final Synthesis Agent.
2. Hybrid Architecture: Strict deterministic safety rules + structured validation.
3. Zero Tolerance for Life-Threat Violations:
   - Downgrading emergency triage is an immediate veto.
   - Omission of 115 emergency directive under emergency lock is an immediate veto.
   - Definitive unsupported diagnosis from afar is blocked.
"""

from __future__ import annotations

import re
from typing import Any

from app.models.intake import CompiledClinicalIntake
from app.models.safety import ClinicalOutputGuardResult, SafetyKernelResult
from app.models.synthesis import FinalSynthesisResult


class ClinicalOutputGuard:
    """Independent post-synthesis gate validating safety before release."""

    @classmethod
    def evaluate_output(
        cls,
        intake: CompiledClinicalIntake,
        safety_kernel: SafetyKernelResult,
        synthesis: FinalSynthesisResult,
    ) -> ClinicalOutputGuardResult:
        violations: list[dict[str, Any]] = []
        reasons: list[str] = []
        answer_lower = synthesis.final_answer.lower()

        # 1. Check Emergency Downgrade
        if safety_kernel.emergency_lock and synthesis.urgency != "EMERGENCY":
            violations.append({
                "code": "EMERGENCY_DOWNGRADE",
                "severity": "CRITICAL",
                "detail": "Safety Kernel emergency lock was active, but final response urgency was downgraded.",
            })
            reasons.append("Phát hiện hạ cấp ca cấp cứu trái phép.")

        # 2. Check Missing Emergency Action
        if safety_kernel.emergency_lock:
            has_115 = "115" in answer_lower or "cấp cứu ngay" in answer_lower
            if not has_115:
                violations.append({
                    "code": "MISSING_EMERGENCY_ACTION",
                    "severity": "CRITICAL",
                    "detail": "Emergency case lacks explicit '115' or 'cấp cứu ngay' instruction.",
                })
                reasons.append("Thiếu chỉ dẫn cấp cứu khẩn cấp 115 bắt buộc.")

        # 3. Check Unsupported Definitive Diagnosis
        unsupported_diagnoses = [
            (r"(chắc chắn|xác định|kết luận)\s+(bạn bị|bị)\s+(huyết khối tĩnh mạch sâu|dvt)", "Khẳng định chẩn đoán DVT từ xa"),
            (r"(chắc chắn|xác định|kết luận)\s+(bạn bị|bị)\s+(ung thư|viêm ruột thừa)", "Khẳng định chẩn đoán bệnh lý nguy hiểm không có xét nghiệm"),
            (r"cam kết\s+100%", "Cam kết 100% trong tư vấn y khoa từ xa"),
        ]
        for pat, desc in unsupported_diagnoses:
            if re.search(pat, answer_lower):
                violations.append({
                    "code": "UNSUPPORTED_DIAGNOSIS",
                    "severity": "HIGH",
                    "detail": f"{desc} bị nghiêm cấm trong tư vấn y tế từ xa.",
                })
                reasons.append(desc)

        # 4. Check Unsafe Medication Advice
        if any("ASPIRIN" in rule for rule in safety_kernel.triggered_rules):
            if "uống aspirin" in answer_lower or "dùng aspirin" in answer_lower:
                violations.append({
                    "code": "UNSAFE_DRUG_ADVICE",
                    "severity": "CRITICAL",
                    "detail": "Aspirin được đề xuất dù có chống chỉ định xuất huyết từ Safety Kernel.",
                })
                reasons.append("Chống chỉ định Aspirin bị vi phạm.")

        # 5. Check Red Flag Omission
        if not synthesis.red_flags:
            violations.append({
                "code": "RED_FLAG_OMISSION",
                "severity": "MEDIUM",
                "detail": "Câu trả lời không chứa danh sách các dấu hiệu cảnh báo cờ đỏ.",
            })
            reasons.append("Thiếu dấu hiệu cảnh báo cờ đỏ.")

        # 6. Check Contradiction with Patient Negations
        for neg in intake.clinical_form.negative_findings:
            raw = neg.raw_span.lower()
            if "không đỏ" in raw and ("bị sưng đỏ" in answer_lower or "chân sưng đỏ" in answer_lower):
                violations.append({
                    "code": "CONTRADICTS_CLINICAL_STATE",
                    "severity": "MEDIUM",
                    "detail": f"Câu trả lời mâu thuẫn với dữ kiện phủ định '{raw}' của người bệnh.",
                })
                reasons.append(f"Mâu thuẫn dữ kiện phủ định: {raw}")

        # Verdict
        has_critical = any(v["severity"] == "CRITICAL" for v in violations)
        has_high = any(v["severity"] == "HIGH" for v in violations)

        if has_critical:
            action = "SAFE_FALLBACK"
            safe = False
        elif has_high or len(violations) > 0:
            action = "REPAIR"
            safe = False
        else:
            action = "PASS"
            safe = True

        return ClinicalOutputGuardResult(
            safe=safe,
            violations=violations,
            action=action,
            reasons=reasons,
        )
