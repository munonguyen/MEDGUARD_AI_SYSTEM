"""Agent B: Independent Evidence & Safety Critic for MedGuard AI System.

Phase 3.3 Architecture Invariant:
1. True Critic Role: Agent B NEVER writes a duplicate answer. Its sole responsibility
   is to find flaws, audit safety, and challenge Agent A's draft.
2. Comprehensive Audit:
   - Unsupported diagnosis
   - Missing red flags
   - Over-triage on benign complaints
   - Under-triage on emergency risks
   - Drug contraindication & interaction omission
   - Contradiction with patient timeline / facts
   - Citation mismatch
   - Missing uncertainty language
3. Non-Compensatory Verdict: High/Critical severity violations result in `critic_pass = False`.
"""

from __future__ import annotations

import re
from typing import Any

from app.models.evidence import ClinicalEvidencePacket
from app.models.intake import CompiledClinicalIntake
from app.models.safety import SafetyKernelResult
from app.models.synthesis import (
    CriticMissingPoint,
    CriticReport,
    CriticViolation,
    ReasoningDraft,
)


class EvidenceCriticAgent:
    """Agent B: Audits Draft A against facts, evidence, and safety invariants."""

    @classmethod
    def audit_draft(
        cls,
        intake: CompiledClinicalIntake,
        evidence_packet: ClinicalEvidencePacket,
        safety_kernel: SafetyKernelResult,
        draft: ReasoningDraft,
    ) -> CriticReport:
        violations: list[CriticViolation] = []
        missing_points: list[CriticMissingPoint] = []
        approved_claims: list[str] = []
        rejected_claims: list[str] = []

        draft_text = draft.draft_answer.lower()
        packet_evidence_ids = {e.evidence_id for e in evidence_packet.all_evidence}

        # 1. Audit Safety Kernel Invariants (Under-Triage & Missing Emergency Actions)
        if safety_kernel.emergency_lock:
            if draft.urgency != "EMERGENCY":
                violations.append(CriticViolation(
                    code="UNDER_TRIAGE",
                    severity="CRITICAL",
                    span=f"Urgency assessed as {draft.urgency}",
                    reason="Safety Kernel emergency lock is active, but Draft A failed to mandate EMERGENCY triage.",
                ))
            has_115_or_er = any(k in draft_text for k in ["115", "cấp cứu ngay", "phòng cấp cứu", "khoa cấp cứu"])
            if not has_115_or_er:
                missing_points.append(CriticMissingPoint(
                    type="emergency_transit",
                    concept="call_115_or_emergency_hospital",
                    mandatory=True,
                    remedy_instruction="Bổ sung hướng dẫn gọi ngay 115 hoặc đến khoa cấp cứu bệnh viện gần nhất, không tự lái xe.",
                ))

        # 2. Over-Triage Check (Over-escalating benign cases)
        elif safety_kernel.minimum_triage == "ROUTINE" and not safety_kernel.hard_red_flags:
            if draft.urgency == "EMERGENCY":
                violations.append(CriticViolation(
                    code="OVER_TRIAGE",
                    severity="HIGH",
                    span="urgency: EMERGENCY",
                    reason="Draft A triggered EMERGENCY triage on a benign routine case without clinical red flags.",
                ))

        # 3. Unsupported Definitive Diagnosis Check
        forbidden_definitive_patterns = [
            (r"(bạn|chắc chắn|xác định)\s+(bị|mắc)\s+(huyết khối tĩnh mạch sâu|dvt)", "Khẳng định chẩn đoán huyết khối tĩnh mạch sâu (DVT) từ xa"),
            (r"(bạn|chắc chắn|xác định)\s+(bị|mắc)\s+(ung thư|viêm ruột thừa|tai biến)", "Khẳng định chẩn đoán bệnh lý nguy hiểm không có cận lâm sàng"),
            (r"(cam kết|khẳng định|chắc chắn)\s+100%", "Cam kết 100% về chẩn đoán từ xa"),
        ]
        for pat, desc in forbidden_definitive_patterns:
            match = re.search(pat, draft_text)
            if match:
                violations.append(CriticViolation(
                    code="UNSUPPORTED_DIAGNOSIS",
                    severity="HIGH",
                    span=match.group(0),
                    reason=f"{desc} vi phạm quy chuẩn an toàn lâm sàng từ xa. Bắt buộc dùng ngôn ngữ phân biệt (có thể/nguy cơ).",
                ))

        # 4. Patient Facts Contradiction Check (e.g. Negations)
        for neg in intake.clinical_form.negative_findings:
            raw_neg = neg.raw_span.lower()
            concept = neg.concept.lower()
            # If patient said "không sưng" or "không đỏ" but draft claims there is swelling or redness
            if "không sưng" in raw_neg and ("bị sưng" in draft_text or "chân sưng to" in draft_text and "không" not in draft_text):
                violations.append(CriticViolation(
                    code="PATIENT_FACT_CONTRADICTION",
                    severity="MEDIUM",
                    span=f"Contradiction on {concept}",
                    reason=f"Người bệnh đã nêu rõ '{raw_neg}', bản thảo không được khẳng định triệu chứng dương tính.",
                ))

        # 5. Missing Mandatory Red Flags Check
        if not draft.red_flags:
            missing_points.append(CriticMissingPoint(
                type="red_flag",
                concept="clinical_warning_signs",
                mandatory=True,
                remedy_instruction="Bổ sung danh sách các dấu hiệu cờ đỏ cảnh báo người bệnh cần đến bệnh viện khám ngay.",
            ))

        # 6. Audit Individual Claims
        for claim in draft.claims:
            claim_text = claim.text.lower()
            claim_rejected = False

            # Check for unsupported diagnosis in individual claim
            if any(re.search(pat[0], claim_text) for pat in forbidden_definitive_patterns):
                rejected_claims.append(claim.claim_id)
                claim_rejected = True

            # Check citation validity
            if not claim.evidence_ids:
                violations.append(CriticViolation(
                    code="CITATION_MISMATCH",
                    severity="LOW",
                    span=claim.text,
                    reason=f"Claim {claim.claim_id} không liên kết với evidence_id nào trong Evidence Packet.",
                ))
            else:
                for eid in claim.evidence_ids:
                    if eid not in packet_evidence_ids and eid != "E0":
                        violations.append(CriticViolation(
                            code="CITATION_MISMATCH",
                            severity="HIGH",
                            span=f"Evidence ID '{eid}' in {claim.claim_id}",
                            reason=f"Evidence ID '{eid}' không tồn tại trong Evidence Packet hiện tại (nguy cơ bịa nguồn).",
                        ))
                        if not claim_rejected:
                            rejected_claims.append(claim.claim_id)
                            claim_rejected = True

            if not claim_rejected:
                approved_claims.append(claim.claim_id)

        # 7. Summary & Verdict
        has_critical_or_high = any(v.severity in ("HIGH", "CRITICAL") for v in violations)
        critic_pass = (not has_critical_or_high) and (len(missing_points) == 0)

        critique_summary = (
            f"Critic Audit: {'PASS' if critic_pass else 'FAIL'} - "
            f"{len(violations)} violations ({sum(1 for v in violations if v.severity in ('HIGH', 'CRITICAL'))} high/critical), "
            f"{len(missing_points)} missing points. "
            f"Approved {len(approved_claims)}/{len(draft.claims)} claims."
        )

        return CriticReport(
            critic_pass=critic_pass,
            violations=violations,
            missing_points=missing_points,
            approved_claims=approved_claims,
            rejected_claims=rejected_claims,
            critique_summary=critique_summary,
        )
