"""Clinical negation extraction for Vietnamese symptom text.

Provides scope-aware negation detection ensuring negated clinical findings
do not falsely trigger red-flag emergency escalations, while properly respecting
clause boundaries (e.g. 'không khó thở nhưng đau ngực').
"""

from __future__ import annotations

import re
from typing import Sequence

from app.services.clinical_text import normalize_search_text


class NegationEngine:
    """Detects negated clinical findings within Vietnamese clinical utterances."""

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

    RAW_CLAUSE_BOUNDARIES = (
        "nhưng",
        "tuy nhiên",
        "song",
        "chứ",
        "mà",
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

    def detect(self, text: str, term: str) -> bool:
        """Return True when a clinical term is negated in its immediate syntactic clause."""
        norm_text = normalize_search_text(text)
        norm_term = normalize_search_text(term).strip()
        if not norm_term:
            return False

        # Find all occurrences of target in normalized text
        matches = [m.start() for m in re.finditer(rf"\b{re.escape(norm_term)}\b", norm_text)]
        if not matches:
            # Fallback to substring matching if word boundary fails
            matches = [m.start() for m in re.finditer(re.escape(norm_term), norm_text)]

        if not matches:
            return False

        for idx in matches:
            # Look back up to 40 characters
            start = max(0, idx - 40)
            prefix = norm_text[start:idx]

            # Find the closest clause boundary before the target
            boundary_pos = -1
            for boundary in self.clause_boundaries:
                # search with word boundaries for words, or literal for punctuation
                if boundary in (";", ".", "!", "?"):
                    b_idx = prefix.rfind(boundary)
                else:
                    m = list(re.finditer(rf"\b{re.escape(boundary)}\b", prefix))
                    b_idx = m[-1].start() if m else -1

                if b_idx > boundary_pos:
                    boundary_pos = b_idx

            # If there is a clause boundary, only search after it
            effective_prefix = prefix[boundary_pos + 1 :] if boundary_pos != -1 else prefix

            # Check if any negation word appears in the effective prefix
            for neg in self.negation_words:
                pattern = rf"\b{re.escape(neg)}\b"
                if re.search(pattern, effective_prefix):
                    # Exception: phrases like 'chua tung bi dau du doi' indicate severity, not absence
                    if neg in ("chua tung", "chua") and any(
                        marker in effective_prefix for marker in ("chua tung bi", "chua bao gio", "truoc gio chua")
                    ):
                        continue
                    return True

        return False

    def extract(self, text: str, terms: Sequence[str]) -> dict[str, bool]:
        """Map each finding in terms present in text to its positive/negative boolean status."""
        norm_text = normalize_search_text(text)
        result: dict[str, bool] = {}
        for term in terms:
            norm_term = normalize_search_text(term)
            if norm_term in norm_text:
                is_negated = self.detect(text, term)
                result[term] = not is_negated
        return result
