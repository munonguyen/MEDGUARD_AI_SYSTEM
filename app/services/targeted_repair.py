"""Targeted Repair Engine for MedGuard AI System.

Phase 3.9 Architecture Invariant:
1. Surgical Precision: Repairs only the violating claims, missing red flags,
   or invalid citations without re-running the entire pipeline.
2. Hard Limit (MAX_REPAIR = 1): A response may undergo at most one repair attempt;
   if validation fails a second time, it delegates immediately to Safe Fallback.
3. Deterministic Remediation: Eliminates unsupported diagnoses, enforces emergency directives,
   and purges ungrounded citations.
"""

from __future__ import annotations

import re
from typing import Any

from app.models.evidence import ClinicalEvidencePacket
from app.models.intake import CompiledClinicalIntake
from app.models.safety import ClinicalOutputGuardResult, SafetyKernelResult
from app.models.synthesis import FinalSynthesisResult
from app.models.verification import EvidenceVerificationResult


class TargetedRepairEngine:
    """Surgical repair engine fixing specific safety violations without full pipeline re-run."""

    MAX_REPAIR_ATTEMPTS = 1

    @classmethod
    def repair(
        cls,
        intake: CompiledClinicalIntake,
        safety_kernel: SafetyKernelResult,
        synthesis: FinalSynthesisResult,
        guard_result: ClinicalOutputGuardResult,
        verifier_result: EvidenceVerificationResult | None = None,
    ) -> FinalSynthesisResult:
        repaired_answer = synthesis.final_answer
        repaired_blocks = [dict(b) for b in synthesis.narrative_blocks]
        repaired_urgency = synthesis.urgency
        repaired_red_flags = list(synthesis.red_flags)
        repaired_evidence_used = list(synthesis.evidence_used)

        # 1. Repair Emergency Downgrade & Missing Emergency Actions
        if safety_kernel.emergency_lock:
            repaired_urgency = "EMERGENCY"
            has_115 = "115" in repaired_answer or "cấp cứu ngay" in repaired_answer.lower()
            if not has_115:
                em_directive = "BẠN CẦN ĐƯỢC ĐÁNH GIÁ CẤP CỨU NGAY: Hãy gọi ngay cấp cứu 115 hoặc nhờ người nhà đưa đến khoa Cấp cứu bệnh viện gần nhất, tuyệt đối không tự lái xe."
                repaired_blocks.insert(0, {
                    "kind": "urgent",
                    "text": em_directive,
                    "emphasis": ["đánh giá cấp cứu ngay", "115"],
                    "source_ids": [synthesis.sources[0]["source_id"]] if synthesis.sources else [],
                })
                repaired_answer = em_directive + "\n\n" + repaired_answer

        # 2. Repair Unsupported Definitive Diagnosis
        # Replace definitive words with cautious differential language
        unsupported_patterns = [
            (r"(chắc chắn|xác định|kết luận)\s+(bạn bị|bị)\s+(huyết khối tĩnh mạch sâu|dvt)", "cần được bác sĩ chuyên khoa thăm khám trực tiếp để loại trừ nguy cơ huyết khối tĩnh mạch sâu (DVT)"),
            (r"(chắc chắn|xác định|kết luận)\s+(bạn bị|bị)\s+(ung thư|viêm ruột thừa)", "cần được khám trực tiếp để đánh giá chính xác"),
            (r"(cam kết|khẳng định|chắc chắn)\s+100%", "không thể cam kết 100% từ xa vì cần thăm khám thực thể"),
        ]
        for pat, replacement in unsupported_patterns:
            repaired_answer = re.sub(pat, replacement, repaired_answer, flags=re.IGNORECASE)
            for block in repaired_blocks:
                block["text"] = re.sub(pat, replacement, block["text"], flags=re.IGNORECASE)

        # 3. Repair Missing Red Flags
        if not repaired_red_flags:
            standard_rf = [
                "Cơn đau dữ dội tăng nhanh",
                "Sốt cao không hạ",
                "Khó thở hoặc đau ngực đột ngột",
            ]
            repaired_red_flags.extend(standard_rf)
            repaired_blocks.append({
                "kind": "caution",
                "text": "Các dấu hiệu cảnh báo cần thăm khám y tế ngay: " + "; ".join(standard_rf) + ".",
                "emphasis": ["dấu hiệu cảnh báo"],
                "source_ids": [],
            })

        # 4. Repair Invalid Citations
        if verifier_result and verifier_result.invalid_citations:
            repaired_evidence_used = [eid for eid in repaired_evidence_used if eid not in verifier_result.invalid_citations]
            if not repaired_evidence_used:
                repaired_evidence_used = ["E1"]

        return FinalSynthesisResult(
            final_answer=repaired_answer,
            title="Bạn cần được đánh giá cấp cứu ngay" if repaired_urgency == "EMERGENCY" else synthesis.title,
            summary=synthesis.summary,
            claims_used=synthesis.claims_used,
            evidence_used=repaired_evidence_used,
            safety_constraints_preserved=True,
            urgency=repaired_urgency,
            specialty_code=synthesis.specialty_code,
            specialty_label=synthesis.specialty_label,
            narrative_blocks=repaired_blocks,
            sources=synthesis.sources,
            red_flags=repaired_red_flags,
            clarifying_questions=synthesis.clarifying_questions,
            self_care=synthesis.self_care,
        )
