"""Dedicated Output Quality Verifier for MedGuard AI System.

Validates the final patient-facing response against the ResponseObligationGraph.
Executes deterministic checklist validation and provides immediate template-based repair
if any critical safety, clarity, or consistency requirement is violated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from app.services.canonical_clinical_state import CanonicalClinicalState
from app.services.clinical_text import normalize_search_text
from app.services.response_obligation import ResponseObligationGraph


@dataclass(frozen=True)
class OutputQualityCheckResult:
    """Detailed result of output quality verification."""
    is_valid: bool
    triage_consistent: bool
    all_required_sections_present: bool
    contains_contradiction: bool
    contains_unsafe_reassurance: bool
    contains_unsupported_diagnosis: bool
    action_is_clear: bool
    language_is_understandable: bool
    missing_obligations: tuple[str, ...] = field(default_factory=tuple)
    violated_forbidden: tuple[str, ...] = field(default_factory=tuple)
    repaired_text: str | None = None


# Pattern matchers for required obligations
_OBLIGATION_PATTERNS = {
    "state_urgency": r"\b(?:cap cuu|khan cap|nguy hiem|canh bao do|tinh trang cap)\b",
    "medical_emergency_action": r"\b(?:115|cap cuu|den ngay|co so y te gan nhat|benh vien|di vien)\b",
    "do_not_delay": r"\b(?:ngay lap tuc|tuc thi|khong duoc tri hoan|khong nen cho|cang som cang tot)\b",
    "self_harm_support": r"\b(?:khung hoang|duong day nong|tam ly|1900|chia se|giup do|nguoi than)\b",
    "do_not_stay_alone": r"\b(?:khong o mot minh|nho nguoi than|nguoi ben canh|nguoi nha)\b",
    "prompt_evaluation_timeframe": r"\b(?:trong ngay|som|trong vong \d+|kham som)\b",
    "supportive_care": r"\b(?:nghi ngoi|uong nuoc|cham soc|theo doi|am ap)\b",
    "when_to_seek_care": r"\b(?:khi nao|dau hieu can di|neu xuat hien|tro nang)\b",
}

# Pattern matchers for forbidden content
_FORBIDDEN_PATTERNS = {
    "home_monitoring": r"(?<!khong )(?<!tuyet doi khong )\b(?:cu o nha theo doi|theo doi tai nha|o nha theo doi)\b",
    "wait_until_tomorrow": r"(?<!khong )(?<!dung )\b(?:doi den mai|de den mai|ngu mot giac|cho sang mai)\b",
    "false_reassurance": r"\b(?:khong sao dau|hoan toan vo hai|khong can lo|chac chan lanh tinh)\b",
    "unsupported_diagnosis": r"\b(?:ban da bi|chac chan ban bi|chuan doan la|ban mac benh)\b",
}


def verify_output_quality(
    text: str,
    obligations: ResponseObligationGraph,
    clinical_state: CanonicalClinicalState | None = None,
) -> OutputQualityCheckResult:
    """Evaluate patient-facing text against clinical response obligations."""
    if not text.strip():
        return OutputQualityCheckResult(
            is_valid=False,
            triage_consistent=False,
            all_required_sections_present=False,
            contains_contradiction=False,
            contains_unsafe_reassurance=False,
            contains_unsupported_diagnosis=False,
            action_is_clear=False,
            language_is_understandable=False,
            missing_obligations=obligations.required_content,
            repaired_text=get_deterministic_template_repair(obligations, clinical_state),
        )

    norm = normalize_search_text(text)
    missing: list[str] = []
    violated: list[str] = []

    # Check required obligations
    for req in obligations.required_content:
        pat = _OBLIGATION_PATTERNS.get(req)
        if pat and not re.search(pat, norm):
            missing.append(req)

    # Check forbidden items
    for forb in obligations.forbidden_content:
        pat = _FORBIDDEN_PATTERNS.get(forb)
        if pat and re.search(pat, norm):
            violated.append(forb)

    # Check triage consistency
    triage_consistent = True
    if obligations.triage == "EMERGENCY":
        if not any(k in norm for k in ("cap cuu", "khan cap", "115", "ngay lap tuc", "benh vien")):
            triage_consistent = False
    elif obligations.triage == "ROUTINE":
        if re.search(r"\b(?:goi 115 ngay|nguy kich tinh mang|tu vong ngay)\b", norm):
            triage_consistent = False

    contains_unsafe_reassurance = "false_reassurance" in violated
    contains_unsupported_diagnosis = "unsupported_diagnosis" in violated
    contains_contradiction = bool(
        ("cap cuu" in norm or "115" in norm)
        and ("theo doi tai nha" in norm or "cho den mai" in norm)
    )

    action_is_clear = bool(
        re.search(r"\b(?:can|hay|nen|uong|di|goi|nghi ngoi|kham)\b", norm)
    )
    language_is_understandable = len(text.split()) < 350  # Prevent overwhelming wall of text

    is_valid = (
        triage_consistent
        and len(missing) == 0
        and len(violated) == 0
        and not contains_contradiction
        and not contains_unsafe_reassurance
        and not contains_unsupported_diagnosis
        and action_is_clear
        and language_is_understandable
    )

    repaired = None
    if not is_valid:
        repaired = get_deterministic_template_repair(obligations, clinical_state)

    return OutputQualityCheckResult(
        is_valid=is_valid,
        triage_consistent=triage_consistent,
        all_required_sections_present=len(missing) == 0,
        contains_contradiction=contains_contradiction,
        contains_unsafe_reassurance=contains_unsafe_reassurance,
        contains_unsupported_diagnosis=contains_unsupported_diagnosis,
        action_is_clear=action_is_clear,
        language_is_understandable=language_is_understandable,
        missing_obligations=tuple(missing),
        violated_forbidden=tuple(violated),
        repaired_text=repaired,
    )


def get_deterministic_template_repair(
    obligations: ResponseObligationGraph,
    clinical_state: CanonicalClinicalState | None = None,
) -> str:
    """Generate an authoritative, safe, deterministic fallback response template."""
    tier = obligations.triage

    if tier == "EMERGENCY":
        crisis_extra = ""
        if obligations.crisis_support_required:
            crisis_extra = (
                "\n\nNếu bạn đang trải qua khủng hoảng tâm lý hoặc cảm giác muốn tự làm tổn thương bản thân, "
                "xin hãy lập tức gọi đến Tổng đài Quốc gia 111 hoặc nhờ người thân bên cạnh ở cùng bạn ngay lúc này. "
                "Bạn không phải đối mặt với điều này một mình."
            )
        return (
            "CẢNH BÁO KHẨN CẤP: Dựa trên các triệu chứng bạn cung cấp, hệ thống nhận diện đây là tình trạng mang dấu hiệu nguy hiểm tính mạng "
            "cần được đánh giá y tế khẩn cấp ngay lập tức.\n\n"
            "HÀNH ĐỘNG CẦN THỰC HIỆN NGAY:\n"
            "1. Gọi ngay Cấp cứu 115 hoặc nhờ người nhà đưa đến khoa Cấp cứu của bệnh viện gần nhất.\n"
            "2. Tuyệt đối KHÔNG tự theo dõi tại nhà, không chờ đợi đến sáng mai và không tự ý dùng các loại thuốc chưa được bác sĩ chỉ định.\n"
            "3. Không ở một mình; hãy báo ngay cho người thân hoặc người xung quanh để được trợ giúp."
            f"{crisis_extra}"
        )

    if tier == "URGENT":
        return (
            "THÔNG BÁO CẦN KHÁM SỚM: Tình trạng triệu chứng của bạn cần được bác sĩ chuyên khoa thăm khám và đánh giá trong ngày (trong vòng 12–24 giờ tới).\n\n"
            "HƯỚNG DẪN CHĂM SÓC:\n"
            "1. Đặt lịch khám tại cơ sở y tế gần nhất trong hôm nay để được chẩn đoán chính xác.\n"
            "2. Nghỉ ngơi hợp lý, theo dõi sát diễn biến triệu chứng.\n"
            "3. NẾU XUẤT HIỆN DẤU HIỆU NẶNG (như khó thở tăng nhanh, đau ngực dữ dội, ngất xỉu hoặc yếu liệt), hãy chuyển sang gọi Cấp cứu 115 ngay lập tức."
        )

    if tier == "ROUTINE":
        return (
            "HƯỚNG DẪN CHĂM SÓC THÔNG THƯỜNG: Hiện tại triệu chứng chưa ghi nhận dấu hiệu nguy kịch trực tiếp đe dọa tính mạng.\n\n"
            "HƯỚNG XỬ TRÍ:\n"
            "1. Nghỉ ngơi, giữ ấm, bù đủ nước và dinh dưỡng nhẹ nhàng.\n"
            "2. Theo dõi tiến triển triệu chứng trong 24–48 giờ tới.\n"
            "3. Đi khám tại cơ sở y tế nếu tình trạng không thuyên giảm hoặc xuất hiện sốt cao, đau tăng dần."
        )

    # UNRESOLVED
    return (
        "THÔNG BÁO CHƯA ĐỦ THÔNG TIN: Dữ liệu bạn cung cấp hiện chưa đủ để xác định mức độ nguy cơ lâm sàng một cách an toàn.\n\n"
        "Vui lòng chia sẻ cụ thể hơn: Triệu chứng xuất hiện từ khi nào? Mức độ đau ra sao? Có kèm theo khó thở, sốt hoặc chóng mặt không?\n"
        "Nếu bạn cảm thấy mệt lả hoặc có dấu hiệu nguy kịch, hãy đến ngay cơ sở y tế gần nhất để kiểm tra trực tiếp."
    )
