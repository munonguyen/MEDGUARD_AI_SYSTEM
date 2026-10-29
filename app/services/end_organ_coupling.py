"""Cross-finding end-organ coupling for Candidate V10.

This layer deliberately reasons over *combinations* of findings.  It does not
promote an isolated word such as ``headache`` or an isolated blood-pressure
number.  A coupling is activated only when independent findings jointly imply
acute organ injury or a time-critical loss of function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Literal

from app.services.clinical_text import contains_affirmed_phrase, normalize_search_text


CouplingDisposition = Literal["ROUTINE", "URGENT", "EMERGENCY"]


@dataclass(frozen=True)
class EndOrganCouplingAssessment:
    disposition: CouplingDisposition = "ROUTINE"
    confidence: float = 0.60
    coupling_ids: tuple[str, ...] = field(default_factory=tuple)
    supporting_findings: tuple[str, ...] = field(default_factory=tuple)
    rationale: str = "Không phát hiện tổ hợp tổn thương cơ quan đích cấp tính."

    @property
    def is_emergency(self) -> bool:
        return self.disposition == "EMERGENCY"


def _extract_bp(norm: str, vitals: dict[str, Any] | None) -> tuple[int | None, int | None]:
    vitals = vitals or {}
    sbp = vitals.get("systolic", vitals.get("sbp"))
    dbp = vitals.get("diastolic", vitals.get("dbp"))
    if sbp is not None or dbp is not None:
        return (int(sbp) if sbp is not None else None, int(dbp) if dbp is not None else None)

    match = re.search(
        r"(?:huyet ap|ha|ap)?\s*[^\d\n]{0,18}\b(\d{2,3})\s*/\s*(\d{2,3})(?:\s*mmhg)?\b",
        norm,
    )
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def evaluate_end_organ_coupling(
    text: str,
    vitals: dict[str, Any] | None = None,
) -> EndOrganCouplingAssessment:
    """Detect high-specificity emergency combinations and indirect deficits."""
    norm = normalize_search_text(text)

    inactive_context = bool(re.search(
        r"\b(?:neu|gia su|doc bao|doc tren mang|tim hieu|nam ngoai|tuan truoc|da khoi|"
        r"khong he bi|khong co trieu chung|hoan toan binh thuong)\b",
        norm,
    ))
    active_contrast = bool(re.search(r"\b(?:nhung gio|nhung hien tai|hien dang|dang bi|dang)\b", norm))
    if inactive_context and not active_contrast:
        return EndOrganCouplingAssessment()

    coupling_ids: list[str] = []
    findings: list[str] = []

    sbp, dbp = _extract_bp(norm, vitals)
    severe_bp = (sbp is not None and sbp >= 180) or (dbp is not None and dbp >= 120)
    severe_headache = (
        any(contains_affirmed_phrase(norm, phrase) for phrase in ("dau dau", "nhuc dau"))
        and any(contains_affirmed_phrase(norm, phrase) for phrase in ("du doi", "kinh khung", "chua tung co", "set danh"))
    )
    has_brain_or_visual_injury = severe_headache or any(
        contains_affirmed_phrase(norm, phrase)
        for phrase in (
            "non oi", "non vot", "non lien tuc", "nhin mo", "roi loan thi luc",
            "mat thi luc", "lu lan", "noi lam nham", "me sang", "co giat",
            "yeu liet", "meo mieng",
        )
    )
    if severe_bp and has_brain_or_visual_injury:
        coupling_ids.append("hypertensive_end_organ_brain_injury")
        findings.extend((f"huyết áp rất cao {sbp or '?'}/{dbp or '?'} mmHg", "triệu chứng thần kinh/nôn/thị giác cấp"))

    sudden_fine_motor_loss = bool(re.search(
        r"\b(?:cam|dang cam|tay|ban tay)\b.{0,55}\b(?:dua|thia|coc|but|dien thoai|do vat)\b"
        r".{0,55}\b(?:roi|rot|tut|khong giu|khong kiem soat)\b|"
        r"\b(?:dua|thia|coc|but|dien thoai|do vat)\b.{0,45}\b(?:roi|rot|tut)\b.{0,35}\b(?:tay|ban tay)\b",
        norm,
    ))
    speech_change = bool(re.search(
        r"\b(?:noi ngap ngung|noi ngat quang|noi ngong|noi kho|u o|khong noi duoc|that ngon)\b",
        norm,
    ))
    acute_marker = bool(re.search(r"\b(?:dot ngot|dot nhien|tu nhien|bong nhien|dang .* thi)\b", norm))
    if sudden_fine_motor_loss and (speech_change or acute_marker):
        coupling_ids.append("acute_indirect_focal_motor_deficit")
        findings.extend(("mất kiểm soát vận động tinh vi đột ngột", "thay đổi lời nói hoặc khởi phát cấp"))

    head_trauma = bool(re.search(
        r"\b(?:nga|va dap|dap dau|dap gay|chan thuong dau|tai nan)\b",
        norm,
    ))
    explosive_headache = bool(re.search(
        r"\b(?:dau dau|nhuc dau|dau buot)\b.{0,55}\b(?:bua ta|bua bo|giang|set danh|"
        r"du doi|khung khiep|vo tung|chua tung)\b|"
        r"\b(?:bua ta|bua bo)\b.{0,45}\b(?:dau|dinh dau|gay)\b",
        norm,
    ))
    if head_trauma and explosive_headache:
        coupling_ids.append("post_traumatic_intracranial_threat")
        findings.extend(("chấn thương đầu/gáy", "đau đầu cực dữ dội kiểu va đập/sét đánh"))

    fever = bool(re.search(r"\b(?:sot|37[.,]8|38(?:[.,]0)?)\b", norm))
    delirium = bool(re.search(r"\b(?:noi lam nham|lam nham vo thuc|me sang|lu lan|ao giac)\b", norm))
    neck_stiffness = bool(re.search(r"\b(?:co|gay)\b.{0,20}\b(?:guong|cung|cung nhac|khong cui)\b", norm))
    if fever and delirium and neck_stiffness:
        coupling_ids.append("meningeal_infection_delirium")
        findings.extend(("sốt", "sảng/lú lẫn", "cổ hoặc gáy gượng cứng"))

    massive_hemoptysis = bool(re.search(
        r"\bho ra mau\b.{0,55}\b(?:tuoi|do au|tung ngum|ngum lon|uot khan|o at|nhieu)\b",
        norm,
    ))
    if massive_hemoptysis:
        coupling_ids.append("major_airway_bleeding")
        findings.append("ho ra máu tươi lượng lớn/tiến triển")

    button_battery = bool(re.search(r"\b(?:pin cuc ao|vien pin|pin do choi)\b", norm))
    aerodigestive_distress = bool(re.search(r"\b(?:nuot|mac|ho sac|sac sua|chay dai|khong nuot|kho tho)\b", norm))
    if button_battery and aerodigestive_distress:
        coupling_ids.append("button_battery_aerodigestive_emergency")
        findings.append("nuốt pin cúc áo kèm dấu hiệu đường thở/đường tiêu hóa")

    sudden_hearing_loss = bool(re.search(
        r"\b(?:dot ngot|dot nhien|tu nhien)\b.{0,45}\b(?:diec dac|diec|mat thinh luc)\b|"
        r"\b(?:mot ben tai|mot tai)\b.{0,35}\b(?:diec dac|mat thinh luc)\b",
        norm,
    ))
    if sudden_hearing_loss:
        coupling_ids.append("sudden_sensorineural_hearing_loss")
        findings.append("mất thính lực cấp tính một bên")

    # Symptomatic rapid rhythm is a combination rule, not a raw pulse cutoff.
    # Use only complete presyncope/syncope concepts here.  Bare "ngat" is
    # intentionally excluded because it is a substring of relations such as
    # "gần ngất" and could otherwise escape local negation in "không gần ngất".
    rapid_rhythm = bool(re.search(
        r"\b(?:tim dap|mach|nhip tim)\b.{0,35}\b(?:loan nhip|loan xa|thinh thich|tren 140|1[4-9]\d)\b",
        norm,
    ))
    presyncope = any(
        contains_affirmed_phrase(norm, phrase)
        for phrase in (
            "hoa mat",
            "choang vang",
            "choang",
            "gan ngat",
            "muon ngat",
            "muon xiu",
            "sap ngat",
            "ngat xiu",
            "bat tinh",
        )
    )
    if rapid_rhythm and presyncope:
        coupling_ids.append("symptomatic_tachyarrhythmia_hypoperfusion")
        findings.append("rối loạn nhịp nhanh kèm tiền ngất/giảm tưới máu")

    if not coupling_ids:
        return EndOrganCouplingAssessment()

    unique_findings = tuple(dict.fromkeys(findings))
    return EndOrganCouplingAssessment(
        disposition="EMERGENCY",
        confidence=0.99,
        coupling_ids=tuple(coupling_ids),
        supporting_findings=unique_findings,
        rationale="Phát hiện tổ hợp dấu hiệu cho thấy tổn thương cơ quan đích hoặc mất chức năng cấp tính cần cấp cứu.",
    )
