"""Clinical negation extraction for Vietnamese symptom text."""

from __future__ import annotations


class NegationEngine:
    NEGATION_WORDS = (
        "không",
        "chưa",
        "không hề",
        "không thấy",
        "không có",
    )

    def detect(self, text: str, term: str) -> bool:
        """Return True when a finding is negated in local context."""
        lowered = text.lower()
        index = lowered.find(term.lower())
        if index == -1:
            return False

        prefix = lowered[max(0, index - 25):index]
        return any(word in prefix for word in self.NEGATION_WORDS)

    def extract(self, text: str, terms: list[str]) -> dict[str, bool]:
        return {
            term: not self.detect(text, term)
            for term in terms
            if term.lower() in text.lower()
        }
