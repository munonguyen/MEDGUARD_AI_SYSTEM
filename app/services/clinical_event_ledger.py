"""Clinical Event Ledger for MedGuard AI V6.

Maintains an immutable, monotonic clinical event ledger across multi-turn
conversation episodes. Prevents critical risks from being silently erased by
symptom easing, patient avoidance, or chat intent drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any

from app.models.clinical_events import (
    ClinicalAssertion,
    ClinicalEvent,
    ClinicalFactSet,
    SeverityLevel,
)
from app.services.clinical_text import normalize_search_text
from app.services.risk_memory import infer_episode_domain, should_start_new_episode


class LedgerEventStatus(str, Enum):
    ACTIVE = "ACTIVE"
    HISTORICALLY_CONFIRMED = "HISTORICALLY_CONFIRMED"
    INVALIDATED = "INVALIDATED"


@dataclass
class LedgerEntry:
    turn_index: int
    event: ClinicalEvent
    status: LedgerEventStatus = LedgerEventStatus.ACTIVE
    invalidation_reason: str | None = None


# Explicit factual retraction markers that genuinely invalidate prior premises
_CORRECTION_PATTERNS = (
    r"\b(nhap nham|go nham|nhin nham|do nham|do lai|kiem tra lai thi|nham cua nguoi khac|nham nguoi)\b",
    r"\b(dinh chinh|toi dinh chinh|nham sang|nham lan|nham vo thuoc|nhin lai vo thuoc|noi nham)\b",
    r"\b(khong phai bi|khong phai uong|khong phai toi|khong phai dau nguc)\b",
    r"\b(chi uong|chua uong|khong uong|rot ra san|con nguyen|uong co 1|chi 1 vien)\b",
    r"\b(me chau|bo chau|phu huynh|nghich may|gui bay|chau nghich|nhan nham)\b",
)

# Domain-specific keywords for targeted event-level invalidation
_TARGETED_RETRACTION_DOMAINS: dict[str, tuple[str, ...]] = {
    "toxicology": (
        r"\b(thuoc|uong thuoc|vo thuoc|uong nham|ngo doc|vien|para|panadol|efferalgan|lieu)\b",
    ),
    "cardiovascular": (
        r"\b(dau nguc|tuc nguc|tim|huyet ap|do nham|do lai huyet ap)\b",
    ),
    "neurology": (
        r"\b(meo mieng|liet|dot quy|tai bien|cung ham)\b",
    ),
    "ophthalmology": (
        r"\b(mat|thi luc|nhin|nham mat)\b",
    ),
    "respiratory": (
        r"\b(kho tho|tho rit|phoi|nghen)\b",
    ),
    "abdomen": (
        r"\b(bung|dau bung|ruot|da day)\b",
    ),
}

# Patient avoidance markers (fear of hospital) that must NEVER erase prior risk
_AVOIDANCE_PATTERNS = (
    r"\b(khong muon di vien|so di vien|ngai di vien|chi muon hoi thuoc|dung bat di vien)\b",
    r"\b(uong nhieu nuoc chanh|o nha theo doi|tu khoi duoc khong|co tu khoi khong)\b",
    r"\b(dung nhac cap cuu|dung bao cap cuu|khong muon phien ha|ngu duoc khong)\b",
)

# Symptom improvement markers that keep the event historically confirmed
_RELIEF_PATTERNS = (
    r"\b(do hon|bot dau|giam dau|do dau|tam thoi do|het dau roi|khong con dau|uong.*thay do|do met|tinh lai|bung hoi em em)\b",
)


class ClinicalEventLedger:
    """Episode-scoped clinical event ledger maintaining risk monotonicity.

    The ledger may be reconstructed from the entire chat history on every API
    request. Therefore it must segment unrelated user complaints while replaying
    history; otherwise a previous back-pain or chest-pain episode can contaminate
    a later abdominal/dizziness episode.
    """

    def __init__(self, episode_id: str = "default_episode") -> None:
        self.episode_id = episode_id
        self.entries: list[LedgerEntry] = []
        self._active_episode_domain: str | None = None
        self._last_user_text: str | None = None

    def _start_new_episode(self, turn_index: int, user_text: str, domain: str | None) -> None:
        """Close prior acute events when a clearly unrelated complaint begins.

        Historical entries remain in the ledger for auditability but are marked
        INVALIDATED for current-episode risk resolution. This does not claim
        that the old symptom was medically false; it only prevents stale acute
        state from governing the new complaint.
        """
        for entry in self.entries:
            if entry.status in (LedgerEventStatus.ACTIVE, LedgerEventStatus.HISTORICALLY_CONFIRMED):
                entry.status = LedgerEventStatus.INVALIDATED
                entry.invalidation_reason = (
                    f"Episode switch before turn {turn_index}: new complaint domain={domain or 'unknown'}; "
                    f"text='{user_text[:60]}'"
                )
        self._active_episode_domain = domain

    def process_turn(
        self,
        turn_index: int,
        user_text: str,
        fact_set: ClinicalFactSet,
    ) -> None:
        """Update the ledger with observations from a new conversation turn."""
        normalized = normalize_search_text(user_text)

        # 0. Episode segmentation. Domain/keyword signals are routing hints only.
        # They never set diagnosis, urgency, specialty, or patient-facing text.
        turn_domain = infer_episode_domain(user_text)
        if self._last_user_text and should_start_new_episode(user_text, self._last_user_text):
            self._start_new_episode(turn_index, user_text, turn_domain)
        elif self._active_episode_domain is None and turn_domain:
            self._active_episode_domain = turn_domain

        # 1. Check for explicit factual retraction
        is_correction = any(bool(re.search(pat, normalized)) for pat in _CORRECTION_PATTERNS)
        if is_correction:
            targeted_systems = [
                sys_name for sys_name, pats in _TARGETED_RETRACTION_DOMAINS.items()
                if any(bool(re.search(p, normalized)) for p in pats)
            ]
            for entry in self.entries:
                if entry.status == LedgerEventStatus.ACTIVE:
                    should_invalidate = False
                    if not targeted_systems:
                        # Global retraction (e.g. "nhắn nhầm người khác", "cháu nghịch máy gửi bậy")
                        should_invalidate = True
                    elif entry.event.organ_system in targeted_systems:
                        should_invalidate = True

                    if should_invalidate:
                        entry.status = LedgerEventStatus.INVALIDATED
                        entry.invalidation_reason = f"Explicit retraction in turn {turn_index}: '{user_text[:60]}'"

        # 2. Check for temporary symptom relief (does NOT invalidate)
        has_relief = any(bool(re.search(pat, normalized)) for pat in _RELIEF_PATTERNS)

        # 3. Add new confirmed events from current turn (must be active patient threats)
        for e in fact_set.active_patient_events:
            # Check if this exact concept was already logged in the active episode.
            existing = [
                ent for ent in self.entries
                if ent.event.concept == e.concept and ent.status != LedgerEventStatus.INVALIDATED
            ]
            if existing:
                if not has_relief:
                    existing[-1].status = LedgerEventStatus.ACTIVE
            else:
                initial_status = LedgerEventStatus.HISTORICALLY_CONFIRMED if has_relief else LedgerEventStatus.ACTIVE
                self.entries.append(LedgerEntry(turn_index=turn_index, event=e, status=initial_status))

        self._last_user_text = user_text

    def get_effective_events(self) -> list[ClinicalEvent]:
        """Return all non-invalidated clinical events for the active episode."""
        return [
            entry.event for entry in self.entries
            if entry.status in (LedgerEventStatus.ACTIVE, LedgerEventStatus.HISTORICALLY_CONFIRMED)
        ]

    def has_active_emergency(self) -> bool:
        """Check if the active episode contains a critical emergency threat."""
        for entry in self.entries:
            if entry.status in (LedgerEventStatus.ACTIVE, LedgerEventStatus.HISTORICALLY_CONFIRMED):
                if entry.event.is_active_patient_threat and (entry.event.is_critical or entry.event.physiologic_consequence in (
                    "catastrophic_vascular_threat",
                    "limb_perfusion_failure",
                    "peritoneal_irritation",
                    "circulatory_compromise",
                    "neuromuscular_airway_compromise",
                    "retinal_or_optic_ischemia",
                    "acute_toxic_metabolic_threat",
                    "exsanguinating_hemorrhage",
                    "metabolic_crisis",
                )):
                    return True
        return False

    def build_effective_fact_set(self) -> ClinicalFactSet:
        """Consolidate all non-invalidated events into an aggregate ClinicalFactSet."""
        effective_events = self.get_effective_events()
        return ClinicalFactSet(
            raw_text=f"Consolidated episode ledger ({len(effective_events)} events)",
            normalized_text="",
            events=tuple(effective_events),
            semantic_coverage=1.0 if effective_events else 0.5,
        )
