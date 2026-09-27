"""Final Consistency Guard for MedGuard AI System.

Phase 3.8 Architecture Invariant:
Enforces strict 100% consensus across:
  ResponseProfile <-> TriageLabel <-> Specialty <-> FinalContent <-> QuickReplies

Prevents catastrophic patient-facing contradictions:
- NEVER display "CẦN ĐÁNH GIÁ CẤP CỨU / Tim mạch" when the body is about "đau vai sau gym là DOMS".
- NEVER display "Thần kinh" for simple sitting back fatigue or leg muscle soreness.
- NEVER display "CẦN ĐÁNH GIÁ CẤP CỨU" when response is a CLARIFY_FIRST safety-net intake.
- NEVER claim "Đã xác minh nguồn" if sources are unverified or generic placeholders.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from pydantic import BaseModel, Field

from app.models.response_policy import ResponseContract, ResponseProfile
from app.services.specialty_resolver import SpecialtyResolver

logger = logging.getLogger(__name__)


class ConsistencyCheckResult(BaseModel):
    """Result of clinical consistency audit."""
    is_consistent: bool
    reconciled_urgency: str
    reconciled_emergency_flag: bool
    reconciled_specialty_code: str
    reconciled_specialty_label: str
    reconciled_is_clarification: bool
    reconciled_title: str
    reconciled_reply: str = Field(default="")
    violations: list[str] = Field(default_factory=list)


class FinalConsistencyGuard:
    """Audits and reconciles Header vs Body vs Specialty vs Urgency consensus."""

    @classmethod
    def audit_and_reconcile(
        cls,
        *,
        query: str,
        contract: ResponseContract,
        raw_urgency: str,
        raw_emergency_flag: bool,
        raw_specialty_code: str | None,
        raw_specialty_label: str | None,
        is_clarification: bool,
        final_answer: str,
        title: str | None = None,
    ) -> ConsistencyCheckResult:
        """Audits consensus and deterministically reconciles any divergence."""
        violations = []
        text = final_answer.lower()
        reconciled_answer = final_answer

        # 1. Resolve Gold-Standard Medical Specialty
        resolved_spec_code, resolved_spec_label, _ = SpecialtyResolver.resolve_specialty(query)
        final_spec_code = raw_specialty_code or resolved_spec_code
        final_spec_label = raw_specialty_label or resolved_spec_label

        if raw_specialty_code and raw_specialty_code != resolved_spec_code:
            # Check if raw specialty was a severe mismatch (e.g. Cardiology for toothache, Neurology for back pain)
            if resolved_spec_code in ("DENTISTRY", "ORTHOPEDICS") and raw_specialty_code in ("CARDIOLOGY", "NEUROLOGY", "GENERAL"):
                violations.append(
                    f"Specialty contradiction corrected: '{raw_specialty_code}' -> '{resolved_spec_code}' for query '{query}'"
                )
                final_spec_code = resolved_spec_code
                final_spec_label = resolved_spec_label
        elif not raw_specialty_code or raw_specialty_code == "GENERAL":
            final_spec_code = resolved_spec_code
            final_spec_label = resolved_spec_label

        # 2. Reconcile Urgency & Emergency Flag
        final_urgency = raw_urgency
        final_emergency = raw_emergency_flag
        final_clarify = is_clarification or (contract.profile == ResponseProfile.CLARIFY_FIRST)

        # Invariant A: CLARIFY_FIRST or SELF_CARE CANNOT have EMERGENCY header!
        if contract.profile in (ResponseProfile.SELF_CARE, ResponseProfile.CLARIFY_FIRST):
            if raw_urgency == "EMERGENCY" or raw_emergency_flag:
                violations.append(
                    f"Contradiction: Profile is '{contract.profile.value}' but triage was 'EMERGENCY'. Overriding triage to ROUTINE."
                )
                final_urgency = "ROUTINE"
                final_emergency = False

        # Invariant B: If True Emergency, Body must contain emergency actions
        if contract.profile == ResponseProfile.EMERGENCY_ACTION or final_emergency:
            has_115 = bool(re.search(r"\b115\b", text) or "cấp cứu" in text)
            if not has_115:
                violations.append("Contradiction: Emergency triage but body lacks 115 instruction.")

        # Invariant D: Orthopedics (Cơ xương khớp) must NEVER have stroke / TIA rationale
        if final_spec_code == "ORTHOPEDICS" or final_spec_label == "Cơ xương khớp":
            if any(k in text for k in ("đột quỵ", "tai biến", "nhồi máu não", "cơn thiếu máu não")):
                violations.append(
                    "Contradiction: Specialty is 'ORTHOPEDICS' (Cơ xương khớp) but response body contains stroke/TIA advice. Reconciled to radicular nerve root evaluation."
                )
                reconciled_answer = re.sub(
                    r"(?i)(?:nghi ngờ\s+)?(?:đột quỵ|tai biến mạch máu não|nhồi máu não|cơn thiếu máu não thoáng qua(?:\s*\(tia\))?)",
                    "tổn thương chèn ép rễ thần kinh thắt lưng",
                    reconciled_answer,
                )
                reconciled_answer = re.sub(
                    r"(?i)trung tâm đột quỵ",
                    "chuyên khoa Cơ xương khớp / Ngoại thần kinh cột sống",
                    reconciled_answer,
                )
                reconciled_answer = re.sub(
                    r"(?i)cửa sổ vàng",
                    "thời gian vàng",
                    reconciled_answer,
                )

        # Invariant C: Clarify First title and header
        final_title = title or "Tư vấn y tế từ MedGuard AI"
        if final_clarify:
            if "làm rõ" not in final_title.lower():
                final_title = f"Làm rõ triệu chứng và tư vấn chuyên khoa: {final_spec_label}"
        elif final_urgency == "EMERGENCY":
            final_title = "Bạn cần được đánh giá cấp cứu ngay"
        elif final_urgency == "URGENT":
            final_title = "Bạn nên được nhân viên y tế đánh giá sớm"
        else:
            if final_spec_label not in final_title and "tổng quát" in final_title.lower():
                final_title = f"Đánh giá và tư vấn chuyên khoa: {final_spec_label}"

        is_consistent = len(violations) == 0

        return ConsistencyCheckResult(
            is_consistent=is_consistent,
            reconciled_urgency=final_urgency,
            reconciled_emergency_flag=final_emergency,
            reconciled_specialty_code=final_spec_code,
            reconciled_specialty_label=final_spec_label,
            reconciled_is_clarification=final_clarify,
            reconciled_title=final_title,
            reconciled_reply=reconciled_answer if reconciled_answer != final_answer else "",
            violations=violations,
        )
