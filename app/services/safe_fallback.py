"""Adaptive Safe Fallback Generator for MedGuard AI System.

Phase 3.10 Architecture Invariant:
1. Adaptive Not Blunt: Replaces rigid old template boilerplate with nuanced,
   compassionate, clinically sound fallback responses.
2. Three Adaptive Tiers:
   - SAFE_EMERGENCY: Immediate 115 emergency call-to-action, cardiac/stroke positioning.
   - SAFE_URGENT: Same-day medical evaluation mandate, symptoms of progression.
   - SAFE_GENERAL: Reassuring home self-care, uncertainty explanation, explicit red flags.
3. Zero Unsupported Diagnosis: Explicitly abstains from definitive labeling from afar.
"""

from __future__ import annotations

from typing import Any, Literal
from app.models.intake import CompiledClinicalIntake
from app.models.safety import SafetyKernelResult
from app.models.synthesis import FinalSynthesisResult


class SafeFallbackGenerator:
    """Generates adaptive, safe fallback responses when synthesis fails or is vetoed."""

    @classmethod
    def generate(
        cls,
        tier: Literal["SAFE_GENERAL", "SAFE_URGENT", "SAFE_EMERGENCY"],
        intake: CompiledClinicalIntake,
        safety_kernel: SafetyKernelResult,
        specialty_code: str = "GENERAL",
        specialty_label: str = "Y tế tổng quát",
        sources: list[dict[str, Any]] | None = None,
    ) -> FinalSynthesisResult:
        sources_list = sources or [
            {
                "source_id": "src_byt_standard",
                "title": "Hướng dẫn chẩn đoán và điều trị (Bộ Y Tế Việt Nam)",
                "publisher": "Bộ Y Tế Việt Nam",
                "authority_tier": "government_health",
                "url": "https://kcb.vn/",
            }
        ]

        if tier == "SAFE_EMERGENCY":
            urgency = "EMERGENCY"
            title = "Bạn cần được đánh giá cấp cứu ngay lập tức"
            summary = "Phát hiện các dấu hiệu đe dọa sinh mạng cần can thiệp y tế tức thời."
            red_flags = safety_kernel.hard_red_flags or ["Đau thắt ngực đè nặng", "Khó thở dữ dội", "Méo miệng, yếu liệt nửa người"]
            narrative = [
                {
                    "kind": "urgent",
                    "text": "BẠN CẦN ĐƯỢC ĐÁNH GIÁ CẤP CỨU NGAY: Hãy gọi ngay 115 hoặc nhờ người nhà đưa đến khoa Cấp cứu bệnh viện gần nhất.",
                    "emphasis": ["đánh giá cấp cứu ngay", "115"],
                },
                {
                    "kind": "caution",
                    "text": "Tuyệt đối không tự lái xe hoặc di chuyển một mình. Hãy ngồi hoặc nằm ở tư thế thoải mái nhất, nới lỏng trang phục và giữ bình tĩnh trong khi chờ nhân viên y tế.",
                    "emphasis": ["không tự lái xe"],
                },
                {
                    "kind": "paragraph",
                    "text": f"Các dấu hiệu cảnh báo khẩn cấp ghi nhận: {', '.join(red_flags)}.",
                },
            ]
            final_answer = "\n\n".join(b["text"] for b in narrative)

        elif tier == "SAFE_URGENT":
            urgency = "URGENT"
            title = f"Khuyến nghị thăm khám bác sĩ chuyên khoa {specialty_label}"
            summary = "Triệu chứng cần được bác sĩ thăm khám và đánh giá trực tiếp sớm trong ngày."
            red_flags = [
                "Cơn đau tăng dần không giảm",
                "Sốt cao liên tục không hạ",
                "Xuất hiện dấu hiệu sưng đau hoặc lan rộng bất thường",
            ]
            narrative = [
                {
                    "kind": "paragraph",
                    "text": f"Dựa trên các triệu chứng bạn cung cấp, MedGuard AI khuyến nghị bạn nên đến cơ sở y tế để được bác sĩ chuyên khoa {specialty_label} thăm khám và chẩn đoán trực tiếp.",
                },
                {
                    "kind": "caution",
                    "text": "Việc tư vấn y tế từ xa không thể thay thế cho thăm khám thực thể. Bạn không nên tự ý dùng các loại thuốc giảm đau, kháng sinh hoặc thuốc tiêm khi chưa có chỉ định của bác sĩ.",
                },
                {
                    "kind": "paragraph",
                    "text": f"Các dấu hiệu cảnh báo cần đi khám ngay: {', '.join(red_flags)}.",
                },
            ]
            final_answer = "\n\n".join(b["text"] for b in narrative)

        else:  # SAFE_GENERAL
            urgency = "ROUTINE"
            title = f"Hướng dẫn theo dõi và chăm sóc sức khỏe ({specialty_label})"
            summary = "Các triệu chứng gợi ý phản ứng thông thường, có thể theo dõi an toàn tại nhà."
            red_flags = [
                "Triệu chứng kéo dài trên 3-5 ngày không thuyên giảm",
                "Sốt cao, đau nhức dữ dội hoặc xuất hiện khó thở",
            ]
            narrative = [
                {
                    "kind": "paragraph",
                    "text": "Tình trạng của bạn có thể xuất phát từ căng cơ cơ học, thời tiết hoặc thay đổi sinh hoạt thông thường.",
                },
                {
                    "kind": "paragraph",
                    "text": "Bạn nên dành thời gian nghỉ ngơi, uống đủ nước ấm, bổ sung dinh dưỡng hợp lý và giữ tinh thần thoải mái.",
                },
                {
                    "kind": "caution",
                    "text": f"Nếu có bất kỳ dấu hiệu bất thường nào như: {', '.join(red_flags)}, bạn hãy đến cơ sở y tế để được bác sĩ thăm khám trực tiếp.",
                },
            ]
            final_answer = "\n\n".join(b["text"] for b in narrative)

        return FinalSynthesisResult(
            final_answer=final_answer,
            title=title,
            summary=summary,
            claims_used=["C_FALLBACK"],
            evidence_used=[sources_list[0].get("source_id", "E1")],
            safety_constraints_preserved=True,
            urgency=urgency,
            specialty_code=specialty_code,
            specialty_label=specialty_label,
            narrative_blocks=narrative,
            sources=sources_list,
            red_flags=red_flags,
            clarifying_questions=["Bạn có đang mắc bệnh nền mãn tính nào không?"],
            self_care=["Nghỉ ngơi hợp lý", "Uống đủ nước"],
        )
