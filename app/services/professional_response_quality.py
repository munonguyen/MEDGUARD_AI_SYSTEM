"""V27.5 patient-surface quality hardening.

This module is deliberately presentation-only.  Clinical authority remains in
Safety Kernel/domain services; Writer remains the sole author of generated
patient prose and Reviewer/Jev remains a non-authoring quality judge.

The pass removes repeated presentation artifacts without introducing, deleting
or re-interpreting clinical facts.  Emergency responses are returned unchanged
because repetition is preferable to weakening an emergency/hard-stop message.
"""

from __future__ import annotations

from difflib import SequenceMatcher
import re
import unicodedata
from typing import Iterable

from app.models.chat import AnswerNarrativeBlock, GroundedAnswer


_MIN_COMPARE_CHARS = 28
_NEAR_DUPLICATE_RATIO = 0.94


def _norm(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", str(value or "").strip().lower())
    normalized = "".join(
        ch for ch in decomposed if unicodedata.category(ch) != "Mn"
    ).replace("đ", "d")
    normalized = re.sub(r"[^a-z0-9%]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _sentences(text: str) -> list[str]:
    """Split conservatively while retaining sentence-final punctuation."""
    value = str(text or "").strip()
    if not value:
        return []
    parts = re.split(r"(?<=[.!?])\s+", value)
    return [part.strip() for part in parts if part.strip()]


def _is_near_duplicate(candidate: str, previous: Iterable[str]) -> bool:
    candidate_norm = _norm(candidate)
    if not candidate_norm:
        return True
    for item in previous:
        item_norm = _norm(item)
        if not item_norm:
            continue
        if candidate_norm == item_norm:
            return True
        if min(len(candidate_norm), len(item_norm)) < _MIN_COMPARE_CHARS:
            continue
        if SequenceMatcher(None, candidate_norm, item_norm).ratio() >= _NEAR_DUPLICATE_RATIO:
            return True
    return False


def _dedupe_sentences(text: str) -> str:
    """Remove only exact/very-near repeated sentences, preserving first order."""
    kept: list[str] = []
    for sentence in _sentences(text):
        if not _is_near_duplicate(sentence, kept):
            kept.append(sentence)
    return " ".join(kept).strip()


def _dedupe_narrative(blocks: list[AnswerNarrativeBlock]) -> list[AnswerNarrativeBlock]:
    """De-duplicate repeated prose while preserving clinical block semantics.

    A block is removed only when the complete remaining text is already present
    with very high similarity.  We never merge blocks with different text, and
    we retain source ids.  Emphasis values that disappeared with a duplicate
    sentence are removed to keep the presentation contract internally valid.
    """
    kept_blocks: list[AnswerNarrativeBlock] = []
    kept_texts: list[str] = []

    for block in blocks:
        text = _dedupe_sentences(block.text)
        if not text:
            continue
        if _is_near_duplicate(text, kept_texts):
            continue
        emphasis = [value for value in block.emphasis if value and value in text]
        kept_blocks.append(
            block.model_copy(
                update={
                    "text": text,
                    "emphasis": list(dict.fromkeys(emphasis)),
                    "source_ids": list(dict.fromkeys(block.source_ids)),
                }
            )
        )
        kept_texts.append(text)

    return kept_blocks


def apply_professional_response_quality(
    answer: GroundedAnswer,
    *,
    urgency: str,
    intent: str,
) -> GroundedAnswer:
    """Apply a bounded final quality pass to patient-visible prose.

    Safety invariants:
    * EMERGENCY is byte-for-byte untouched by this module.
    * Structured clinical claims/actions/safety notes/questions are untouched.
    * No new medical statement is generated.
    * Only duplicate sentences/blocks already present are removed.

    ``intent`` is accepted explicitly so callers cannot accidentally apply this
    pass without carrying the resolved clinical context.  It is intentionally
    not used to infer content.
    """
    del intent  # context is required by contract, not used for clinical inference

    if str(urgency or "ROUTINE").upper() == "EMERGENCY":
        return answer

    summary = _dedupe_sentences(answer.summary)
    narrative = _dedupe_narrative(list(answer.narrative))

    return answer.model_copy(
        update={
            "summary": summary,
            "narrative": narrative,
        }
    )


def narrative_repetition_ratio(answer: GroundedAnswer) -> float:
    """Return a deterministic diagnostic ratio for CI/unit tests.

    This is an observability helper, not a clinical gate.  A value of 0 means no
    exact/near duplicate narrative block remains after normalization.
    """
    texts = [block.text for block in answer.narrative if _norm(block.text)]
    if not texts:
        return 0.0
    duplicate = 0
    seen: list[str] = []
    for text in texts:
        if _is_near_duplicate(text, seen):
            duplicate += 1
        else:
            seen.append(text)
    return duplicate / len(texts)
