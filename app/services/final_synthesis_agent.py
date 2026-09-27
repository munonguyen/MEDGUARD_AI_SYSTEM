"""Final Synthesis Agent for MedGuard AI System.

Phase 3.7 Architecture Upgrade:
1. Selective Merging: Integrates verified claims from Agent A (Reasoner),
   Agent B (Critic), and Jev Context Planner.
2. Invariant Safety Preserved:
   - Must NOT invent new medical claims or diagnoses.
   - Must NOT alter Safety Kernel emergency lock.
   - Must NOT invent citations.
   - Must filter out any claims rejected by the Critic.
3. ResponseContract Compliance:
   - Follows ResponseProfile (EMERGENCY_ACTION, CLARIFY_FIRST, SELF_CARE, MEDICATION_SAFETY).
   - Enforces empathetic, patient-centered tone and health literacy.
   - Eliminates repetitive mechanical 115 panic alerts and internal debug metadata.
"""

from __future__ import annotations

import logging
from typing import Any

from app.models.evidence import ClinicalEvidencePacket
from app.models.intake import CompiledClinicalIntake
from app.models.response_policy import (
    ClinicalResponseContext,
    ResponseContract,
    ResponseProfile,
)
from app.models.safety import SafetyKernelResult
from app.models.synthesis import (
    ArbitrationDecision,
    CriticReport,
    FinalSynthesisResult,
    JevMicroJudgment,
    ReasoningDraft,
)
from app.services.response_policy_engine import ResponsePolicyEngine
from app.services.safe_fallback import SafeFallbackGenerator

logger = logging.getLogger(__name__)


class FinalSynthesisAgent:
    """Final Synthesis Agent: Synthesizes final verified response conforming to ResponseContract."""

    @classmethod
    def synthesize(
        cls,
        intake: CompiledClinicalIntake,
        evidence_packet: ClinicalEvidencePacket,
        safety_kernel: SafetyKernelResult,
        draft: ReasoningDraft,
        critic: CriticReport,
        jev: JevMicroJudgment,
        arbitration: ArbitrationDecision,
        contract: ResponseContract | None = None,
        context_plan: ClinicalResponseContext | None = None,
    ) -> FinalSynthesisResult:
        # 1. Handle Safe Fallback Action
        if arbitration.action == "SAFE_FALLBACK":
            fallback_tier = arbitration.fallback_policy or (
                "SAFE_EMERGENCY" if safety_kernel.emergency_lock else "SAFE_GENERAL"
            )
            return SafeFallbackGenerator.generate(
                tier=fallback_tier,  # type: ignore[arg-type]
                intake=intake,
                safety_kernel=safety_kernel,
                specialty_code=draft.specialty_code,
                specialty_label=draft.specialty_label,
                sources=draft.sources,
            )

        # 2. Derive ResponseContract if not provided
        if contract is None:
            contract = ResponsePolicyEngine.evaluate(
                query=intake.raw_query,
                safety_kernel=safety_kernel,
                user_intent="triage",
            )

        # 3. Enforce Safety Urgency
        final_urgency = "EMERGENCY" if safety_kernel.emergency_lock else draft.urgency

        # 4. Filter Approved Claims & Remove Rejected Ones
        approved_claims = [c for c in draft.claims if c.claim_id not in critic.rejected_claims]
        claims_used = [c.claim_id for c in approved_claims]
        evidence_used = list({eid for c in approved_claims for eid in c.evidence_ids if eid != "E0"})

        # 5. Integrate Missing Points from Critic
        final_red_flags = list(draft.red_flags)
        for mp in critic.missing_points:
            if mp.type == "red_flag" and mp.remedy_instruction not in final_red_flags:
                final_red_flags.append(mp.remedy_instruction)

        # 6. Assemble Narrative Blocks according to ResponseProfile
        narrative_blocks: list[dict[str, Any]] = []

        if contract.profile == ResponseProfile.EMERGENCY_ACTION:
            # Professional, calm, firm emergency guidance without mechanical 4x repetitions
            em_call = (
                "Các dấu hiệu bạn mô tả có thể là tình huống cần được cấp cứu y tế khẩn cấp. "
                "Hãy gọi ngay cấp cứu 115 hoặc nhờ người nhà đưa bạn đến khoa Cấp cứu bệnh viện gần nhất."
            )
            narrative_blocks.append({
                "kind": "urgent",
                "text": em_call,
                "emphasis": ["cấp cứu y tế", "115"],
                "source_ids": [draft.sources[0]["source_id"]] if draft.sources else [],
            })

            em_steps = (
                "Trong lúc chờ nhân viên y tế đến:\n"
                "- Dừng mọi hoạt động gắng sức, ngồi hoặc nằm nghỉ ở tư thế thoải mái và an toàn nhất.\n"
                "- Nhờ người thân ở cạnh hỗ trợ nếu có thể, tuyệt đối không tự lái xe.\n"
                "- Không tự ý dùng thêm thuốc giảm đau, hạ áp trừ khi đã được bác sĩ hướng dẫn cho tình huống này."
            )
            narrative_blocks.append({
                "kind": "paragraph",
                "text": em_steps,
                "emphasis": ["nghỉ ngơi", "không tự lái xe", "không tự dùng thuốc"],
                "source_ids": [],
            })

            if draft.follow_up_questions:
                em_q = (
                    "Nếu có thể trả lời mà không làm chậm trễ việc gọi cấp cứu: "
                    + draft.follow_up_questions[0]
                )
                narrative_blocks.append({
                    "kind": "paragraph",
                    "text": em_q,
                    "emphasis": [],
                    "source_ids": [],
                })

            title = "Bạn cần được đánh giá cấp cứu ngay"
            summary = "Phát hiện dấu hiệu cấp cứu y tế. Đã hướng dẫn gọi 115 và các bước an toàn lúc chờ."

        elif contract.profile == ResponseProfile.CLARIFY_FIRST:
            # Empathetic clarification with critical safety net (BookingCare style)
            if approved_claims:
                explanation = " ".join(c.text for c in approved_claims)
            else:
                explanation = draft.clinical_interpretation

            narrative_blocks.append({
                "kind": "paragraph",
                "text": explanation,
                "emphasis": [],
                "source_ids": [draft.sources[0]["source_id"]] if draft.sources else [],
            })

            if final_red_flags:
                safety_net_text = (
                    "Điều quan trọng trước tiên là kiểm tra các dấu hiệu nguy hiểm: "
                    + "; ".join(final_red_flags)
                    + ". Nếu có một trong các dấu hiệu này, bạn hãy đến cơ sở y tế hoặc gọi 115 ngay."
                )
                narrative_blocks.append({
                    "kind": "caution",
                    "text": safety_net_text,
                    "emphasis": ["dấu hiệu nguy hiểm", "115"],
                    "source_ids": [],
                })

            if draft.follow_up_questions:
                clarify_text = "Để định hướng cụ thể hơn, bạn có thể cho mình biết: " + " ".join(draft.follow_up_questions)
                narrative_blocks.append({
                    "kind": "paragraph",
                    "text": clarify_text,
                    "emphasis": [],
                    "source_ids": [],
                })

            title = f"Làm rõ thông tin lâm sàng: {draft.specialty_label}"
            summary = "Tiếp nhận triệu chứng ban đầu, thiết lập lưới an toàn và hướng dẫn làm rõ chi tiết."

        else:
            # Standard Clinical / Self-Care Consultation
            if approved_claims:
                clinical_text = " ".join(c.text for c in approved_claims)
            else:
                clinical_text = draft.clinical_interpretation

            narrative_blocks.append({
                "kind": "paragraph",
                "text": clinical_text,
                "emphasis": [],
                "source_ids": [draft.sources[0]["source_id"]] if draft.sources else [],
            })

            if draft.self_care:
                self_care_text = (
                    "Hướng dẫn chăm sóc và theo dõi tại nhà trong 1–2 ngày: "
                    + "; ".join(draft.self_care)
                    + "."
                )
                narrative_blocks.append({
                    "kind": "paragraph",
                    "text": self_care_text,
                    "emphasis": ["1–2 ngày", "chăm sóc tại nhà"],
                    "source_ids": [draft.sources[-1]["source_id"]] if len(draft.sources) > 1 else [],
                })

            if final_red_flags:
                rf_text = (
                    "Cần đi khám chuyên khoa sớm nếu xuất hiện một trong các dấu hiệu: "
                    + "; ".join(final_red_flags)
                    + "."
                )
                narrative_blocks.append({
                    "kind": "caution",
                    "text": rf_text,
                    "emphasis": ["dấu hiệu cờ đỏ", "khám sớm"],
                    "source_ids": [],
                })

            if draft.follow_up_questions:
                q_text = "Bạn có thể chia sẻ thêm: " + " ".join(draft.follow_up_questions)
                narrative_blocks.append({
                    "kind": "paragraph",
                    "text": q_text,
                    "emphasis": [],
                    "source_ids": [],
                })

            title = f"Tư vấn chuyên khoa: {draft.specialty_label}"
            summary = draft.summary if hasattr(draft, "summary") and draft.summary else (clinical_text[:200] + "...")

        full_answer = "\n\n".join(b["text"] for b in narrative_blocks)

        return FinalSynthesisResult(
            final_answer=full_answer,
            title=title,
            summary=summary,
            claims_used=claims_used,
            evidence_used=evidence_used,
            safety_constraints_preserved=True,
            urgency=final_urgency,
            specialty_code=draft.specialty_code,
            specialty_label=draft.specialty_label,
            narrative_blocks=narrative_blocks,
            sources=draft.sources,
            red_flags=final_red_flags,
            clarifying_questions=draft.follow_up_questions,
            self_care=draft.self_care,
        )
