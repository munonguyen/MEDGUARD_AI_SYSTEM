"""Multi-turn Clinical Risk Memory for MedGuard AI.

Maintains risk monotonicity across multi-turn conversation episodes.
Prevents anchoring on earlier benign conclusions and prevents dangerous
downgrading when symptoms temporarily ease or patient reports partial relief.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from app.services.clinical_text import normalize_search_text
from app.services.triage_resolver import URGENCY_RANK, highest_urgency


@dataclass(frozen=True)
class RiskState:
    highest_urgency: str = "ROUTINE"
    red_flags: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    turn_count: int = 0
    correction_applied: bool = False


# Explicit user corrections / fact retractions that invalidate prior premises
_CORRECTION_MARKERS: tuple[str, ...] = (
    "nhap nham",
    "go nham",
    "nhin nham",
    "do nham",
    "do lai thi",
    "kiem tra lai thi",
    "nham cua nguoi khac",
    "nham nguoi",
    "hoi cho nguoi khac",
    "khong phai toi",
    "dinh chinh",
    "toi dinh chinh",
    "nham sang",
    "nham lan",
    "nham vo thuoc",
    "nhin lai vo thuoc",
    "khong phai bi",
    "khong phai uong",
    "khong phai toi tieu ra mau",
    "khong phai tieu ra mau",
    "khong phai dau nguc",
    "khong phai uong 10 vien",
    "khong phai uong ca vi",
    "chi uong 1 vien",
    "rot ra san chu khong phai",
    "nham so do",
)

# Symptom improvement / temporary relief markers that MUST NOT erase prior emergency peak
_SYMPTOM_IMPROVEMENT_MARKERS: tuple[str, ...] = (
    "do hon",
    "bot dau",
    "giam dau",
    "do dau",
    "tam thoi do",
    "het dau roi",
    "het dau nua",
    "khong dau nua",
    "khong con dau nua",
    "khong dau nguc nua",
    "het dau nguc roi",
    "khong con dau",
    "khong con trieu chung",
    "uong panadol thay do",
    "nghi ngoi thay do",
    "do met",
    "tinh lai roi",
    "tinh tao roi",
    "da bot",
    "do kho tho",
)


# Patient avoidance / fear of hospital markers that attempt to cancel referral without factual replacement
_AVOIDANCE_MARKERS: tuple[str, ...] = (
    "dung bat di vien",
    "dung bao di vien",
    "khong muon di vien",
    "so di vien",
    "ngai di vien",
    "chi muon hoi thuoc",
    "dung nhac cap cuu",
    "dung bao cap cuu",
    "toi so di vien",
    "dung bao toi di vien",
    "khong muon bi",
    "dung nhac nua",
)

# Substantive replacement fact patterns that prove a genuine factual correction
_REPLACEMENT_FACT_PATTERNS: tuple[str, ...] = (
    r"\b(chi uong|chua uong|khong uong|rot ra san|con nguyen|uong co 1|chi 1 vien)\b",
    r"\b(do lai|kiem tra lai|nhiet ke|huyet ap)\b.*?\b(\d+([.,]\d+)?|binh thuong|ha sot|khong sot)\b",
    r"\b(thuc ra|that ra|chi la|chi bi)\b.*?\b(moi co|dau co|nguoi khac|hoi ho|hoi cho|chuot rut|nhe|cang co)\b",
    r"\b(nham sang|khong phai toi|hoi ho nguoi nha|benh cua me|benh cua bo|benh cua con|chua tung)\b",
    r"\b(chi dau co vai|chi moi tay|chi hoi che do an|chua tung bi|nguoi nha bi)\b",
)


def is_explicit_correction(text: str) -> bool:
    """Detect if the user is actively retracting an erroneous fact WITH a substantive replacement.
    
    Clinical Invariant:
      - Bare retractions (e.g. 'À tôi nói nhầm') WITHOUT a replacement fact are REJECTED.
      - Patient avoidance maneuvers (e.g. 'đừng bảo tôi đi viện', 'không muốn bị đau ngực nữa') NEVER downgrade.
      - Symptom cessation/relief disguised as correction ('nói nhầm... thực ra tôi không đau ngực nữa')
        is classified as SYMPTOM IMPROVEMENT and REJECTED as a correction, maintaining the emergency hold.
      - A valid correction MUST invalidate the historical premise (e.g. 'I never had chest pain; asked for another person').
    """
    norm = normalize_search_text(text)

    # 1. Defend against patient avoidance / reluctance / wishful thinking attacks
    if any(avoid in norm for avoid in _AVOIDANCE_MARKERS):
        return False
    if bool(re.search(r"\b(?:khong muon|dung nhac|so bi|ngai)\s+(?:dau|di vien|cap cuu|nhap vien)\b", norm)):
        return False

    # 2. Defend against symptom improvement / cessation disguised as 'correction'
    # E.g. 'Tôi nói nhầm chuyện đau ngực. Thực ra tôi không đau ngực nữa.'
    # Even if prefixed with 'nói nhầm', reporting that the pain has stopped/eased is SYMPTOM IMPROVEMENT,
    # NOT premise invalidation!
    if any(marker in norm for marker in _SYMPTOM_IMPROVEMENT_MARKERS) or bool(
        re.search(r"\b(?:khong|het|do|bot|khong con)\s+(?:dau|met|kho tho|tuc nguc|dau nguc|kho chiu)\s*(?:nua|roi|hon)?\b", norm)
    ):
        return False

    # 3. Reject bare retractions with no replacement fact
    bare_retraction_phrases = (
        "a toi noi nham",
        "toi noi nham",
        "noi nham",
        "noi nham thoi",
        "nham roi",
        "toi noi lon",
        "noi lon",
        "nham",
    )
    if norm.strip() in bare_retraction_phrases:
        return False

    # 4. Check for substantive correction: must have correction indicator + replacement fact
    has_correction_marker = any(marker in norm for marker in _CORRECTION_MARKERS) or bool(
        re.search(r"\b(?:xin loi|nham|dinh chinh)\b.{0,40}\b(?:khong phai|nhap nham|do lai|nhin lai|chua tung)\b", norm)
    )
    if not has_correction_marker:
        return False

    # Check for substantive replacement premise
    has_replacement = any(bool(re.search(pat, norm)) for pat in _REPLACEMENT_FACT_PATTERNS)
    # Also valid if user explains it was someone else, never had it, or a lab/medication typo
    if not has_replacement:
        has_replacement = any(k in norm for k in ("nguoi khac", "nguoi nha", "hoi ho", "vo thuoc", "do lai", "chi uong 1", "chi bi moi", "tap ta", "chua tung bi", "chua tung"))

    return has_replacement


def is_symptom_improvement(text: str) -> bool:
    """Detect if the patient merely reports transient symptomatic relief or symptom cessation."""
    norm = normalize_search_text(text)
    return any(marker in norm for marker in _SYMPTOM_IMPROVEMENT_MARKERS) or bool(
        re.search(r"\b(?:khong|het|do|bot|khong con)\s+(?:dau|met|kho tho|tuc nguc|dau nguc|kho chiu)\s*(?:nua|roi|hon)?\b", norm)
    )


def merge_risk(
    previous: RiskState | None,
    *,
    current_urgency: str,
    current_red_flags: list[str] | None = None,
    current_reasons: list[str] | None = None,
    is_correction: bool = False,
) -> RiskState:
    """Merge current turn risk into cumulative episode state.
    
    Clinical Protocol Rules:
      1. Confirmed new danger -> escalate immediately (MAX).
      2. Explicit correction -> invalidate conflicting old fact, recompute to current turn.
      3. Mere symptom improvement -> DO NOT automatically remove prior red flag peak.
    """
    previous = previous or RiskState()

    if is_correction:
        # Invalidate erroneous prior premise and recompute risk from the corrected narrative
        return RiskState(
            highest_urgency=current_urgency,
            red_flags=current_red_flags or [],
            reasons=list(dict.fromkeys((current_reasons or []) + ["explicit_user_correction_applied"])),
            turn_count=previous.turn_count + 1,
            correction_applied=True,
        )

    # Monotonic conservative MAX
    highest = highest_urgency(previous.highest_urgency, current_urgency)
    merged_flags = list(dict.fromkeys(previous.red_flags + (current_red_flags or [])))
    merged_reasons = list(dict.fromkeys(previous.reasons + (current_reasons or [])))

    return RiskState(
        highest_urgency=highest,
        red_flags=merged_flags,
        reasons=merged_reasons,
        turn_count=previous.turn_count + 1,
        correction_applied=previous.correction_applied,
    )


# Anatomical domain markers for detecting topic shifts
_DOMAIN_MARKERS: dict[str, tuple[str, ...]] = {
    "cardiovascular": (
        "tuc nguc", "dau nguc", "nang nguc", "dau that nguc", "vung tim", "mach vanh",
        "danh trong nguc", "hoi hop", "loan nhip", "nhoi mau", "tim dap nhanh",
    ),
    "dental": (
        "rang", "nhuc rang", "dau rang", "sau rang", "nuou", "loi", "tuy rang", "nho rang",
        "rang khon", "e buot", "buot rang", "viem loi", "viem tuy", "cung ham",
    ),
    "musculoskeletal": (
        "tap gym", "gym", "tap ta", "tang co", "doms", "moi co", "cang co", "chuot rut",
        "co nguc", "dau co", "gian co", "bong gan", "khop goi", "dau lung", "co bap",
        "co lien suon", "dau nhuc co", "dau vai", "moi vai", "vai gay", "co vai gay",
        "bap chan", "cang bap chan", "ngoi lau", "ngoi may tinh", "moi lung", "that lung",
    ),
    "neurology": (
        "meo mieng", "meo mat", "dot quy", "tai bien", "co giat", "dong kinh", "liet nua nguoi",
        "yeu nua nguoi", "noi ngong", "u o", "dong tu gian",
    ),
    "dermatology": (
        "di ung da", "noi me day", "ngua da", "phat ban", "mun nhot", "man do", "viem da",
    ),
    "ent": (
        "dau hong", "viem hong", "ngat mui", "so mui", "viem xoang", "u tai", "chay nuoc mui",
    ),
    "gastrointestinal": (
        "dau da day", "trao nguoc", "o chua", "day bung", "tieu chay", "tao bon", "dau bung",
    ),
    "ophthalmology": (
        "dau mat", "moi mat", "do mat", "kho mat", "viem ket mac",
    ),
}

_ACUTE_RED_FLAGS: tuple[str, ...] = (
    "kho tho", "lan tay trai", "lan tay", "bop nghet", "de nang",
    "va mo hoi", "ngat xiu", "ngat", "hon me", "meo mieng", "yeu liet",
    "khong tho duoc", "tim dap loan", "115", "soc phan ve",
)


def detect_clinical_domain(text: str) -> str | None:
    """Detect anatomical organ system or clinical domain from text."""
    norm = normalize_search_text(text)
    if any(k in norm for k in ("lan tay trai", "bop nghet", "de nang", "kho tho", "hoi chung vanh", "nhoi mau", "tim dap nhanh")):
        if any(k in norm for k in ("nguc", "tim", "kho tho")):
            return "cardiovascular_emergency"
    for domain, keywords in _DOMAIN_MARKERS.items():
        if any(kw in norm for kw in keywords):
            return domain
    return None


def should_start_new_episode(latest_text: str, previous_text: str | None = None) -> bool:
    """Determine if user explicitly switches to a completely new unrelated problem or clinical domain."""
    norm = normalize_search_text(latest_text)
    explicit_markers = (
        "yeu cau moi",
        "trieu chung moi",
        "van de moi",
        "khong lien quan",
        "van de khac",
        "chuyen khac",
        "hoi ve nguoi khac",
        "nguoi khac",
        "da khoi han",
        "chuyen hom truoc da khoi",
        "benh truoc da khoi",
        "chuyen cu da xong",
    )
    if any(marker in norm for marker in explicit_markers):
        return True

    # If previous_text is provided, check for domain shift
    if previous_text:
        latest_domain = detect_clinical_domain(latest_text)
        prev_domain = detect_clinical_domain(previous_text)
        if latest_domain and prev_domain and latest_domain != prev_domain:
            has_acute_red_flag = any(flag in norm for flag in _ACUTE_RED_FLAGS)
            if not has_acute_red_flag:
                return True

    return False

