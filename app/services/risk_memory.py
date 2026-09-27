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


# Episode detection is intentionally a lexical/semantic routing aid only.  These
# markers never determine diagnosis, urgency, specialty, or patient-facing text.
# They only decide whether previous acute symptom state belongs to the current
# complaint.  Keep markers specific enough to represent a chief complaint, not
# generic associated symptoms such as nausea or fatigue.
_EPISODE_DOMAIN_MARKERS: dict[str, tuple[str, ...]] = {
    "dental": (
        "dau rang",
        "e buot rang",
        "nhuc rang",
        "sung loi",
        "sung nuou",
    ),
    "gastrointestinal": (
        "dau bung",
        "dau thuong vi",
        "thuong vi",
        "vung tren ron",
        "tren ron",
        "dau da day",
        "nong rat da day",
        "nong rat bung",
        "o chua",
        "tieu chay",
        "tao bon",
        "phan den",
        "non ra mau",
    ),
    "cardiorespiratory": (
        "dau nguc",
        "tuc nguc",
        "nang nguc",
        "dau that nguc",
        "danh trong nguc",
        "hoi hop",
        "kho tho",
        "hut hoi",
    ),
    "neurovestibular": (
        "chong mat",
        "choang vang",
        "hoa mat",
        "toi sam",
        "sap ngat",
        "ngat xiu",
        "dau dau",
        "meo mieng",
        "noi ngong",
        "kho noi",
    ),
    "musculoskeletal_spine": (
        "dau lung",
        "moi lung",
        "that lung",
        "dau co",
        "moi co",
        "dau vai",
        "vai gay",
        "dau khop",
        "dau bap chan",
        "dau chan",
        "te chan",
        "lan xuong chan",
        "lan xuong mong",
        "yeu chan",
    ),
    "dermatology": (
        "phat ban",
        "noi man",
        "ngua da",
        "zona",
        "benh ghe",
        "nam da",
    ),
}

_EPISODE_CONTINUATION_MARKERS: tuple[str, ...] = (
    "van ",
    "van con",
    "van bi",
    "con ",
    "ngoai ra",
    "them nua",
    "kem theo",
    "cung luc",
    "va gio",
    "trieu chung nay",
    "con dau nay",
    "luc nay",
    "tu luc do",
)


def infer_episode_domain(text: str) -> str | None:
    """Return a lightweight chief-complaint domain for episode routing only.

    This is deliberately *not* a clinical diagnosis classifier.  Keyword hits
    are treated as weak routing signals so unrelated acute complaints do not
    inherit stale symptoms, triage floors, specialties, or quick replies.
    """
    norm = normalize_search_text(text)
    matches: list[tuple[int, str]] = []
    for domain, markers in _EPISODE_DOMAIN_MARKERS.items():
        for marker in markers:
            pos = norm.find(marker)
            if pos >= 0:
                matches.append((pos, domain))
                break
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    return matches[0][1]


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


def should_start_new_episode(latest_text: str, previous_text: str | None = None) -> bool:
    """Determine whether the latest user turn starts an unrelated clinical episode.

    Explicit switch phrases remain authoritative.  When a previous user turn is
    provided, a strong chief-complaint domain change is also treated as a new
    episode unless the latest text explicitly indicates continuation/addition.
    This keeps keywords in their intended role: routing signals only, never
    clinical truth or response-template selectors.
    """
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

    if not previous_text:
        return False

    # Phrases such as "vẫn...", "ngoài ra...", "kèm theo..." indicate that
    # the user is extending the current episode rather than replacing it.
    if any(marker in norm for marker in _EPISODE_CONTINUATION_MARKERS):
        return False

    previous_domain = infer_episode_domain(previous_text)
    current_domain = infer_episode_domain(latest_text)
    return bool(
        previous_domain
        and current_domain
        and previous_domain != current_domain
    )
