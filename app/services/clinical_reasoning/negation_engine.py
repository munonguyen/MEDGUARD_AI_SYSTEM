"""Clinical negation extraction for Vietnamese symptom text.

Provides scope-aware negation detection ensuring negated clinical findings do
not falsely trigger red-flag escalation. V28.2 adds mention-specific evaluation
so a symptom can legitimately change state inside one utterance, for example:
"lúc đầu không khó thở nhưng giờ khó thở".
"""

from __future__ import annotations

import re
from typing import Sequence

from app.services.clinical_text import normalize_search_text


class NegationEngine:
    """Detect negated clinical findings within Vietnamese clinical utterances."""

    RAW_NEGATION_WORDS = (
        "không hề",
        "không thấy",
        "không có",
        "chưa từng",
        "không bị",
        "loại trừ",
        "chẳng có",
        "chưa",
        "không",
        "hết",
    )

    # Besides classic conjunctions, temporal/contrast markers terminate the
    # previous negation scope. This prevents "lúc đầu không khó thở, giờ khó
    # thở" and "không đau dữ dội, chỉ hơi đau" from inheriting stale negation.
    RAW_CLAUSE_BOUNDARIES = (
        "nhưng",
        "tuy nhiên",
        "song",
        "chứ",
        "mà",
        "giờ",
        "hiện tại",
        "bây giờ",
        "chỉ",
        ";",
        ".",
        "!",
        "?",
    )

    def __init__(self) -> None:
        self.negation_words = tuple(
            dict.fromkeys(
                [w for w in self.RAW_NEGATION_WORDS]
                + [normalize_search_text(w) for w in self.RAW_NEGATION_WORDS]
            )
        )
        self.clause_boundaries = tuple(
            dict.fromkeys(
                [b for b in self.RAW_CLAUSE_BOUNDARIES]
                + [normalize_search_text(b) for b in self.RAW_CLAUSE_BOUNDARIES]
            )
        )

    def _is_negated_index(self, norm_text: str, idx: int, scope_chars: int | None = 40) -> bool:
        """Evaluate negation immediately before one normalized mention index."""
        start = max(0, idx - scope_chars) if scope_chars is not None else 0
        prefix = norm_text[start:idx]

        boundary_pos = -1
        # A comma alone can join a negated list. A comma followed by a new
        # subject/temporal predicate instead starts a new assertion, e.g.
        # "không ho, tôi vừa hít khí độc". Do not carry the earlier negation.
        new_assertions = list(re.finditer(r",\s*(?:toi|da|vua|dang)\b", prefix))
        if new_assertions:
            boundary_pos = new_assertions[-1].start()
        for boundary in self.clause_boundaries:
            if boundary in (";", ".", "!", "?"):
                b_idx = prefix.rfind(boundary)
            else:
                matches = list(re.finditer(rf"\b{re.escape(boundary)}\b", prefix))
                b_idx = matches[-1].start() if matches else -1
            if b_idx > boundary_pos:
                boundary_pos = b_idx

        effective_prefix = prefix[boundary_pos + 1 :] if boundary_pos != -1 else prefix
        for neg in self.negation_words:
            if re.search(rf"\b{re.escape(neg)}\b", effective_prefix):
                # "chưa từng bị đau dữ dội như vậy" expresses novelty/severity,
                # not absence of the symptom itself.
                if neg in ("chua tung", "chua") and any(
                    marker in effective_prefix
                    for marker in ("chua tung bi", "chua bao gio", "truoc gio chua")
                ):
                    continue
                return True
        return False

    def is_negated_at(self, text: str, normalized_index: int, *, scope_chars: int | None = 40) -> bool:
        """Return negation status for one mention at an index in normalized text.

        Callers that obtain match positions from ``normalize_search_text(text)``
        should use this method instead of aggregating all occurrences.
        ``scope_chars=None`` retains the whole clause for long exposure lists;
        contrast, temporal and explicit new-assertion boundaries still apply.
        """
        norm_text = normalize_search_text(text)
        if normalized_index < 0 or normalized_index > len(norm_text):
            return False
        return self._is_negated_index(norm_text, normalized_index, scope_chars)

    def mention_statuses(self, text: str, term: str) -> list[tuple[int, bool]]:
        """Return ``(normalized_index, is_negated)`` for every term mention."""
        norm_text = normalize_search_text(text)
        norm_term = normalize_search_text(term).strip()
        if not norm_term:
            return []
        matches = list(re.finditer(rf"\b{re.escape(norm_term)}\b", norm_text))
        if not matches:
            matches = list(re.finditer(re.escape(norm_term), norm_text))
        return [(m.start(), self._is_negated_index(norm_text, m.start())) for m in matches]

    def detect(self, text: str, term: str) -> bool:
        """Return True when all observed mentions of ``term`` are negated.

        For a single mention this preserves the original API semantics. For
        mixed mentions, an affirmed mention prevents the finding from being
        globally classified as absent; callers needing temporal/latest state
        should use :meth:`mention_statuses` or :meth:`is_negated_at`.
        """
        statuses = self.mention_statuses(text, term)
        return bool(statuses) and all(is_negated for _, is_negated in statuses)

    def extract(self, text: str, terms: Sequence[str]) -> dict[str, bool]:
        """Map each finding in terms present in text to aggregate presence state."""
        result: dict[str, bool] = {}
        for term in terms:
            statuses = self.mention_statuses(text, term)
            if statuses:
                result[term] = not all(is_negated for _, is_negated in statuses)
        return result
