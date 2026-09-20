"""Single-Pass Clinical Response Generator for Tri-Gate Architecture.

Design Invariant:
  clinical state → decision → ONE final response generation.
  Strictly writes the user-facing explanation ONCE after the Deterministic
  Final Safety Resolver has finalized the triage and policy constraints.
  Eliminates token waste and multi-round rewrite latencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.chat import AnswerNarrativeBlock, GroundedAnswer
from app.services.tri_gate_resolver import FinalResolution


@dataclass(frozen=True)
class SingleResponse:
    reply_text: str
    narrative_blocks: tuple[AnswerNarrativeBlock, ...]
    grounded_answer: GroundedAnswer | None
    policy_compliant: bool
    word_count: int


def render_single_clinical_response(
    resolution: FinalResolution,
    symptoms_text: str,
    *,
    specialty_guidance: str | None = None,
    red_flags: list[str] | None = None,
) -> SingleResponse:
    """Generate the user-facing clinical response in a single pass."""
    blocks: list[AnswerNarrativeBlock] = []
    red_flag_items = red_flags or []

    if resolution.final_triage == "EMERGENCY":
        p1 = (
            "Dựa trên các dấu hiệu cảnh báo nguy kịch bạn vừa mô tả, đây là tình trạng cấp cứu y tế khẩn cấp. "
            "Bạn cần lập tức gọi cấp cứu 115 hoặc nhờ người thân đưa đến khoa Cấp cứu của bệnh viện gần nhất ngay bây giờ."
        )
        p2 = (
            "TUYỆT ĐỐI KHÔNG ở nhà tự xử trí, không tự uống thuốc giảm đau hay trì hoãn cấp cứu. "
            "Trong thời gian chờ nhân viên y tế hoặc phương tiện vận chuyển, hãy giữ người bệnh nằm yên ở tư thế an toàn, "
            "nới lỏng quần áo và không cho ăn uống."
        )
        blocks.append(AnswerNarrativeBlock(text=p1, kind="urgent", emphasis=["115", "Cấp cứu"]))
        blocks.append(AnswerNarrativeBlock(text=p2, kind="caution", emphasis=["TUYỆT ĐỐI KHÔNG ở nhà"]))

    elif resolution.final_triage == "URGENT":
        p1 = (
            f"Các triệu chứng bạn mô tả cho thấy cơ thể đang có dấu hiệu bất thường cần được can thiệp sớm. "
            f"Bạn nên sắp xếp đến cơ sở y tế hoặc phòng khám chuyên khoa để được bác sĩ trực tiếp thăm khám và làm xét nghiệm trong ngày."
        )
        if specialty_guidance:
            p1 += f" {specialty_guidance}"

        p2 = (
            "Trong lúc này, hãy tạm dừng các hoạt động gắng sức và theo dõi sát. "
            "Nếu xuất hiện các dấu hiệu trở nặng đột ngột như khó thở tăng, đau dữ dội, ngất xỉu, lạnh toát chân tay, hãy chuyển sang cấp cứu 115 ngay."
        )
        blocks.append(AnswerNarrativeBlock(text=p1, kind="paragraph", emphasis=["trong ngày", "thăm khám"]))
        blocks.append(AnswerNarrativeBlock(text=p2, kind="caution", emphasis=["cấp cứu 115"]))

    else:  # ROUTINE
        p1 = (
            "Hiện tại chưa ghi nhận các dấu hiệu đe dọa sinh mạng hoặc cảnh báo cấp bách. "
            "Tình trạng này thường phù hợp với quá tải cơ học, phản ứng kích ứng nhẹ hoặc căng thẳng tạm thời. "
            "Bạn nên ưu tiên nghỉ ngơi, uống đủ nước ấm, thả lỏng cơ thể và tạm dừng các công việc nặng."
        )
        p2 = (
            "Bạn có thể tiếp tục theo dõi tại nhà. Tuy nhiên, nếu cơn đau hay triệu chứng không thuyên giảm sau 2-3 ngày, "
            "hoặc xuất hiện sốt cao, nôn ói liên tục, tê yếu chi hoặc đau nhức dữ dội, bạn hãy đến cơ sở y tế để được kiểm tra kỹ lưỡng."
        )
        blocks.append(AnswerNarrativeBlock(text=p1, kind="paragraph", emphasis=["nghỉ ngơi", "uống đủ nước"]))
        blocks.append(AnswerNarrativeBlock(text=p2, kind="caution", emphasis=["theo dõi tại nhà"]))

    reply_text = "\n\n".join(b.text for b in blocks)
    words = len(reply_text.split())

    # Check policy compliance
    forbid = resolution.response_policy.get("forbid_phrases", [])
    compliant = not any(phrase in reply_text.lower() for phrase in forbid)

    grounded = GroundedAnswer(
        title=f"Đánh giá Lâm sàng Tri-Gate ({resolution.final_triage})",
        summary=blocks[0].text if blocks else "",
        narrative=blocks,
        decision_basis="versioned_rules",
        evidence_state="bounded_result",
        sources=[],
    )

    return SingleResponse(
        reply_text=reply_text,
        narrative_blocks=tuple(blocks),
        grounded_answer=grounded,
        policy_compliant=compliant,
        word_count=words,
    )
