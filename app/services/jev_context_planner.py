"""Jev Context Planner for MedGuard AI System.

Phase 3.7 Architecture Upgrade:
Jev transitions from a dictatorial triage judge to a sophisticated Clinical Context Editor.

Role:
- Does NOT decide global emergency levels (reserved for Safety Kernel & Response Policy).
- Acts as a clinical context curator: plans optimal depth, empathetic tone, high-value
  explanations, essential red flags, focused follow-up questions, and explicit concepts to avoid.
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
from app.services.canonical_clinical_state import CanonicalClinicalState

logger = logging.getLogger(__name__)


class JevContextPlanner:
    """Clinical Context Planner planning context, depth, tone, and guidance boundaries."""

    @classmethod
    def plan(
        cls,
        *,
        contract: ResponseContract,
        intake: CompiledClinicalIntake | None = None,
        clinical_state: CanonicalClinicalState | None = None,
        safety_kernel: SafetyKernelResult | None = None,
        evidence_packet: ClinicalEvidencePacket | None = None,
    ) -> ClinicalResponseContext:
        """Generates the ClinicalResponseContext guiding Agent A, Critic B, and Final Synthesis."""
        profile = contract.profile

        # 1. EMERGENCY ACTION
        if profile == ResponseProfile.EMERGENCY_ACTION:
            return ClinicalResponseContext(
                tone="calm_firm_emergency",
                depth="action_focused",
                primary_goal="emergency_escalation_and_safety",
                explain=[
                    "Dấu hiệu lâm sàng nghiêm trọng có thể là tình huống cấp cứu y tế",
                    "Cần được can thiệp bởi đội ngũ y bác sĩ chuyên khoa ngay lập tức",
                ],
                highlight_red_flags=[
                    "Đau ngực dữ dội đè nghẹt, lan hàm/vai/cánh tay",
                    "Khó thở cấp tính, vã mồ hôi, choáng váng hoặc ngất",
                    "Yếu liệt tay chân, méo mặt, nói ngọng đột ngột",
                ],
                ask_next=[
                    "Triệu chứng bắt đầu từ bao lâu và bạn có đang khó thở hoặc choáng không? (Chỉ trả lời nếu không làm chậm trễ việc gọi cấp cứu)",
                ],
                avoid=[
                    "Lặp lại cụm từ 'gọi 115' nhiều lần một cách máy móc",
                    "Đưa ra các chẩn đoán phân biệt phức tạp gây trì hoãn cấp cứu",
                    "Khuyên tự dùng thuốc lung tung (như aspirin, thuốc hạ áp) khi chưa rõ nguyên nhân",
                ],
                adaptive_quick_replies=contract.adaptive_quick_replies,
            )

        # 2. CLARIFY_FIRST (e.g. Chest pain without flags, or Vague muscle pain)
        if profile == ResponseProfile.CLARIFY_FIRST:
            if "tuc nguc" in (intake.raw_query if intake else "") or "dau nguc" in (intake.raw_query if intake else ""):
                return ClinicalResponseContext(
                    tone="calm_reassuring_vigilant",
                    depth="moderate",
                    primary_goal="safety_net_and_clarification",
                    explain=[
                        "Cảm giác tức ngực có thể bắt nguồn từ nhiều nguyên nhân đa dạng (cơ thành ngực, trào ngược thực quản, căng thẳng lo âu, hoặc các vấn đề tim mạch/hô hấp)",
                        "Chỉ từ một câu mô tả ngắn ban đầu chưa thể khẳng định ngay nguyên nhân chính xác",
                    ],
                    highlight_red_flags=[
                        "Đau bóp nghẹt dữ dội, đau kéo dài không đỡ",
                        "Đau lan lên cổ, hàm, lưng hoặc xuống cánh tay trái",
                        "Khó thở, vã mồ hôi lạnh, choáng váng, tụt huyết áp",
                    ],
                    ask_next=[
                        "Cảm giác tức ngực bắt đầu từ khi nào và xảy ra khi nghỉ ngơi hay khi vận động?",
                        "Cơn đau có lan đi đâu và bạn có thấy khó thở hoặc choáng váng không?",
                    ],
                    avoid=[
                        "Khẳng định chẩn đoán nhồi máu cơ tim hoặc loại trừ hoàn toàn nguy cơ tim mạch",
                        "Đổ template cấp cứu 115 dồn dập khi người dùng chỉ mới nói 1 câu ngắn",
                        "Dùng từ ngữ kỹ thuật như ESI, Gateway, Triage",
                    ],
                    adaptive_quick_replies=contract.adaptive_quick_replies,
                )

            # Muscle pain without location
            return ClinicalResponseContext(
                tone="warm_empathetic",
                depth="brief_to_moderate",
                primary_goal="anatomical_clarification_and_initial_comfort",
                explain=[
                    "Đau mỏi cơ là triệu chứng rất phổ biến, có thể do căng cơ, vận động gắng sức, tư thế hoặc thay đổi thời tiết",
                    "Cần xác định vị trí giải phẫu cụ thể để có định hướng chăm sóc và chuyên khoa phù hợp",
                ],
                highlight_red_flags=[
                    "Đau dữ dội không cử động được",
                    "Sưng to, biến dạng hoặc bầm tím lan rộng",
                    "Kèm tê bì, mất cảm giác hoặc yếu liệt",
                ],
                ask_next=[
                    "Bạn đang bị đau cơ ở vị trí nào trên cơ thể (lưng, vai gáy, chân, tay, hay toàn thân)?",
                    "Cơn đau xuất hiện sau vận động, chấn thương hay tự nhiên xuất hiện?",
                ],
                avoid=[
                    "Chốt ngay nhãn 'Theo dõi tại nhà' khi chưa rõ vị trí",
                    "Đưa ra các chẩn đoán vội vàng",
                    "Ngôn ngữ máy móc hành chính",
                ],
                adaptive_quick_replies=contract.adaptive_quick_replies,
            )

        # 3. SELF_CARE (e.g. Specific muscle pain in arm/leg/neck)
        if profile == ResponseProfile.SELF_CARE:
            return ClinicalResponseContext(
                tone="supportive_clinical",
                depth="moderate",
                primary_goal="self_care_education_and_monitoring",
                explain=[
                    "Căng cơ hoặc viêm gân nhẹ sau vận động quá mức, mang vác nặng hoặc làm việc lặp lại",
                    "Tổn thương vi mô sau va chạm nhẹ hoặc sai tư thế sinh hoạt",
                ],
                highlight_red_flags=[
                    "Đau dữ dội không giảm khi nghỉ ngơi",
                    "Sưng to, bầm tím rõ, biến dạng, không nhấc/duỗi được chi",
                    "Đau kèm tê bì, yếu tay/chân, cầm nắm hoặc đi lại khó khăn",
                ],
                ask_next=[
                    "Cơn đau xuất hiện sau vận động nặng, sau va đập chấn thương hay tự nhiên xuất hiện?",
                    "Hiện tại vùng đau có bị sưng nóng, đỏ hay tê bì không?",
                ],
                avoid=[
                    "Khuyên dùng thuốc giảm đau kháng viêm liều cao tự ý",
                    "Bỏ qua các dấu hiệu chấn thương hoặc biến dạng",
                    "Hiển thị trạng thái kỹ thuật Gateway hay Jev",
                ],
                adaptive_quick_replies=contract.adaptive_quick_replies,
            )

        # 4. MEDICATION SAFETY
        if profile == ResponseProfile.MEDICATION_SAFETY:
            return ClinicalResponseContext(
                tone="clear_objective",
                depth="moderate",
                primary_goal="medication_safety_and_interaction_audit",
                explain=[
                    "Cơ chế tương tác dược lý giữa các hoạt chất",
                    "Ảnh hưởng đối với chức năng gan, thận hoặc bệnh nền",
                ],
                highlight_red_flags=[
                    "Dấu hiệu quá liều, dị ứng thuốc (phát ban, sưng môi mắt, khó thở)",
                    "Chảy máu bất thường hoặc tụt huyết áp nghiêm trọng",
                ],
                ask_next=[
                    "Bạn đã uống các thuốc này cùng lúc chưa và liều lượng cụ thể là bao nhiêu?",
                ],
                avoid=[
                    "Kê đơn hoặc tự ý chỉ định đổi thuốc thay bác sĩ điều trị",
                    "Ngôn ngữ phán xét bệnh nhân",
                ],
                adaptive_quick_replies=contract.adaptive_quick_replies,
            )

        # 5. GENERAL CLINICAL EXPLANATION / DEFAULT
        return ClinicalResponseContext(
            tone="supportive_clinical",
            depth="moderate",
            primary_goal="clinical_understanding_and_safe_guidance",
            explain=[
                "Giải thích bản chất triệu chứng theo kiến thức y khoa chuẩn mực",
                "Các bước xử trí an toàn bước đầu tại nhà",
            ],
            highlight_red_flags=[
                "Triệu chứng tăng nặng nhanh không thuyên giảm",
                "Có kèm sốt cao, khó thở, hoặc suy giảm ý thức",
            ],
            ask_next=[
                "Triệu chứng đã kéo dài bao lâu và có kèm theo biểu hiện nào khác không?",
            ],
            avoid=[
                "Chẩn đoán khẳng định chắc chắn",
                "Bỏ quên khuyến cáo thăm khám trực tiếp",
            ],
            adaptive_quick_replies=contract.adaptive_quick_replies,
        )
