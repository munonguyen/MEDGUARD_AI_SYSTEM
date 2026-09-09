"""Conservative phrase matching for deterministic clinical rules."""

from __future__ import annotations

import re
import unicodedata


_NEGATION_PREFIX = re.compile(
    r"(?:^|[\s,;:.!?])"
    r"(?:không|khong|ko|chưa|chua|phủ\s+nhận|phu\s+nhan)"
    r"(?:\s+(?:có|co|hề|he|bị|bi|thấy|thay|từng|tung|triệu\s+chứng|trieu\s+chung))*"
    r"\s*$",
    re.IGNORECASE,
)


def normalize_search_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.lower())
    return "".join(
        character for character in decomposed if unicodedata.category(character) != "Mn"
    ).replace("đ", "d")


def contains_affirmed_phrase(text: str, phrase: str) -> bool:
    """Return true when at least one phrase occurrence is not directly negated.

    This intentionally handles only explicit local negation. Ambiguous or remote
    negation is left for clarification rather than inferred by the rule engine.
    """
    if not phrase:
        return False
    left_boundary = r"(?<![a-z0-9])" if phrase[0].isalnum() else ""
    right_boundary = r"(?![a-z0-9])" if phrase[-1].isalnum() else ""
    pattern = re.compile(f"{left_boundary}{re.escape(phrase)}{right_boundary}", re.IGNORECASE)
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 64) : match.start()]
        if not _NEGATION_PREFIX.search(prefix):
            return True
    return False
