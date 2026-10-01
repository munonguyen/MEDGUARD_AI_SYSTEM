"""Multi-turn Clinical Risk Memory for MedGuard AI.

Maintains risk monotonicity across multi-turn conversation episodes.
Prevents anchoring on earlier benign conclusions and prevents dangerous
downgrading when symptoms temporarily ease or patient reports partial relief.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from app.services.clinical_text import contains_affirmed_phrase, normalize_search_text
from app.services.triage_resolver import URGENCY_RANK, highest_urgency


@dataclass(frozen=True)
class RiskState:
    highest_urgency: str = "ROUTINE"
    red_flags: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    turn_count: int = 0
    correction_applied: bool = False


_CORRECTION_MARKERS: tuple[str, ...] = (
    "nhap nham", "go nham", "nhin nham", "do nham", "do lai thi", "kiem tra lai thi",
    "nham cua nguoi khac", "nham nguoi", "hoi cho nguoi khac", "khong phai toi", "dinh chinh",
    "toi dinh chinh", "nham sang", "nham lan", "nham vo thuoc", "nhin lai vo thuoc",
    "khong phai bi", "khong phai uong", "khong phai toi tieu ra mau", "khong phai tieu ra mau",
    "khong phai dau nguc", "khong phai uong 10 vien", "khong phai uong ca vi", "chi uong 1 vien",
    "rot ra san chu khong phai", "nham so do",
)

_SYMPTOM_IMPROVEMENT_MARKERS: tuple[str, ...] = (
    "do hon", "bot dau", "giam dau", "do dau", "tam thoi do", "het dau roi", "het dau nua",
    "khong dau nua", "khong con dau nua", "khong dau nguc nua", "het dau nguc roi", "khong con dau",
    "khong con trieu chung", "uong panadol thay do", "nghi ngoi thay do", "do met", "tinh lai roi",
    "tinh tao roi", "da bot", "do kho tho",
)

_AVOIDANCE_MARKERS: tuple[str, ...] = (
    "dung bat di vien", "dung bao di vien", "khong muon di vien", "so di vien", "ngai di vien",
    "chi muon hoi thuoc", "dung nhac cap cuu", "dung bao cap cuu", "toi so di vien", "dung bao toi di vien",
    "khong muon bi", "dung nhac nua",
)

_REPLACEMENT_FACT_PATTERNS: tuple[str, ...] = (
    r"\b(chi uong|chua uong|khong uong|rot ra san|con nguyen|uong co 1|chi 1 vien)\b",
    r"\b(do lai|kiem tra lai|nhiet ke|huyet ap)\b.*?\b(\d+([.,]\d+)?|binh thuong|ha sot|khong sot)\b",
    r"\b(thuc ra|that ra|chi la|chi bi)\b.*?\b(moi co|dau co|nguoi khac|hoi ho|hoi cho|chuot rut|nhe|cang co)\b",
    r"\b(nham sang|khong phai toi|hoi ho nguoi nha|benh cua me|benh cua bo|benh cua con|chua tung)\b",
    r"\b(chi dau co vai|chi moi tay|chi hoi che do an|chua tung bi|nguoi nha bi)\b",
)

_EPISODE_DOMAIN_MARKERS: dict[str, tuple[str, ...]] = {
    "dental": ("dau rang", "e buot rang", "nhuc rang", "sung loi", "sung nuou"),
    "gastrointestinal": (
        "dau bung", "dau thuong vi", "thuong vi", "vung tren ron", "tren ron", "dau da day",
        "nong rat da day", "nong rat bung", "bung con cao", "con cao", "kho chiu o bung", "o chua",
        "tieu chay", "tao bon", "phan den", "non ra mau",
    ),
    "cardiorespiratory": (
        "dau nguc", "tuc nguc", "nang nguc", "dau that nguc", "danh trong nguc", "hoi hop", "kho tho", "hut hoi",
    ),
    "neurovestibular": (
        "chong mat", "choang vang", "hoa mat", "toi sam", "sap ngat", "ngat xiu", "dau dau", "meo mieng",
        "noi ngong", "kho noi",
    ),
    "peripheral_joint": (
        "dau khop tay", "dau cac khop tay", "dau khop ngon tay", "dau khop ngon", "dau co tay",
        "dau khop co tay", "dau khop goi", "dau dau goi", "dau khop co chan", "sung khop", "khop sung",
        "khop nong do", "cung khop buoi sang", "dau nhieu khop", "dau da khop", "dau khop",
    ),
    "musculoskeletal_spine": (
        "dau lung", "moi lung", "that lung",
        # Avoid diacritic-stripped homographs: "môi có" normalizes to
        # ``moi co`` and "đâu có" to ``dau co``.  The old generic markers could
        # therefore turn allergic lip swelling or ordinary negation into a neck
        # complaint.  Require explicit neck/shoulder context instead.
        "dau co vai", "dau co gay", "moi co vai", "moi co gay", "co vai gay",
        "dau vai", "vai gay", "dau bap chan", "dau chan", "te chan", "lan xuong chan", "lan xuong mong", "yeu chan",
    ),
    "dermatology": ("phat ban", "noi man", "ngua da", "zona", "benh ghe", "nam da"),
}

_EPISODE_CONTINUATION_MARKERS: tuple[str, ...] = (
    "van ", "van con", "van bi", "ngoai ra", "them nua", "kem theo", "cung luc", "va gio",
    "trieu chung nay", "con dau nay", "luc nay", "tu luc do",
)


def infer_episode_domain(text: str) -> str | None:
    """Return a lightweight chief-complaint domain for episode routing only."""
    norm = normalize_search_text(text)
    matches: list[tuple[int, str]] = []
    for domain, markers in _EPISODE_DOMAIN_MARKERS.items():
        for marker in markers:
            pos = norm.find(marker)
            if pos >= 0 and contains_affirmed_phrase(norm, marker):
                matches.append((pos, domain))
                break
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    return matches[0][1]


def is_explicit_correction(text: str) -> bool:
    normalized = normalize_search_text(text)
    return any(marker in normalized for marker in _CORRECTION_MARKERS)


def is_symptom_improvement(text: str) -> bool:
    normalized = normalize_search_text(text)
    return any(marker in normalized for marker in _SYMPTOM_IMPROVEMENT_MARKERS)


def is_avoidance_request(text: str) -> bool:
    normalized = normalize_search_text(text)
    return any(marker in normalized for marker in _AVOIDANCE_MARKERS)


def has_substantive_replacement_fact(text: str) -> bool:
    normalized = normalize_search_text(text)
    return any(re.search(pattern, normalized) for pattern in _REPLACEMENT_FACT_PATTERNS)


def should_start_new_episode(previous_text: str, latest_text: str) -> bool:
    if is_explicit_correction(latest_text) and has_substantive_replacement_fact(latest_text):
        return True
    latest = normalize_search_text(latest_text)
    if any(marker in latest for marker in _EPISODE_CONTINUATION_MARKERS):
        return False
    previous_domain = infer_episode_domain(previous_text)
    latest_domain = infer_episode_domain(latest_text)
    return bool(previous_domain and latest_domain and previous_domain != latest_domain)


def update_risk_state(
    previous: RiskState | None,
    *,
    current_urgency: str,
    red_flags: list[str] | None = None,
    reasons: list[str] | None = None,
    latest_text: str = "",
) -> RiskState:
    prior = previous or RiskState()
    correction = is_explicit_correction(latest_text) and has_substantive_replacement_fact(latest_text)
    if correction:
        return RiskState(
            highest_urgency=current_urgency,
            red_flags=list(red_flags or []),
            reasons=list(reasons or []),
            turn_count=prior.turn_count + 1,
            correction_applied=True,
        )
    return RiskState(
        highest_urgency=highest_urgency(prior.highest_urgency, current_urgency),
        red_flags=list(dict.fromkeys([*prior.red_flags, *(red_flags or [])])),
        reasons=list(dict.fromkeys([*prior.reasons, *(reasons or [])])),
        turn_count=prior.turn_count + 1,
        correction_applied=False,
    )
