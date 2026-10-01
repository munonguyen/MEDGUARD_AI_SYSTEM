"""V27.5 patient-surface quality hardening.

This module is deliberately presentation-only. Clinical authority remains in
Safety Kernel/domain services; Writer remains the sole author of generated
patient prose and Reviewer/Jev remains a non-authoring quality judge.

The pass removes repeated presentation artifacts without introducing, deleting
or re-interpreting clinical facts. Emergency responses are returned unchanged
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


def _duplicate_index(candidate: str, previous: Iterable[str]) -> int | None:
    """Return the first exact/very-near duplicate index, if any."""
    candidate_norm = _norm(candidate)
    if not candidate_norm:
        return 0
    for index, item in enumerate(previous):
        item_norm = _norm(item)
        if not item_norm:
            continue
        if candidate_norm == item_norm:
            return index
        if min(len(candidate_norm), len(item_norm)) < _MIN_COMPARE_CHARS:
            continue
        if SequenceMatcher(None, candidate_norm, item_norm).ratio() >= _NEAR_DUPLICATE_RATIO:
            return index
    return None


def _is_near_duplicate(candidate: str, previous: Iterable[str]) -> bool:
    return _duplicate_index(candidate, previous) is not None


def _dedupe_sentences(text: str) -> str:
    """Remove only exact/very-near repeated sentences, preserving first order."""
    kept: list[str] = []
    for sentence in _sentences(text):
        if not _is_near_duplicate(sentence, kept):
            kept.append(sentence)
    return " ".join(kept).strip()


def _dedupe_narrative(blocks: list[AnswerNarrativeBlock]) -> list[AnswerNarrativeBlock]:
    """De-duplicate prose while preserving clinical presentation provenance.

    If a complete block repeats an existing block, its source ids are merged
    into the retained block rather than discarded. This keeps source/citation
    provenance intact while presenting the prose once. Emphasis is retained
    only when it still occurs in the retained text.
    """
    kept_blocks: list[AnswerNarrativeBlock] = []
    kept_texts: list[str] = []

    for block in blocks:
        text = _dedupe_sentences(block.text)
        if not text:
            continue

        duplicate_at = _duplicate_index(text, kept_texts)
        if duplicate_at is not None and duplicate_at < len(kept_blocks):
            retained = kept_blocks[duplicate_at]
            merged_sources = list(dict.fromkeys([*retained.source_ids, *block.source_ids]))
            merged_emphasis = list(
                dict.fromkeys(
                    value
                    for value in [*retained.emphasis, *block.emphasis]
                    if value and value in retained.text
                )
            )
            kept_blocks[duplicate_at] = retained.model_copy(
                update={
                    "source_ids": merged_sources,
                    "emphasis": merged_emphasis,
                }
            )
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
    pass without carrying the resolved clinical context. It is intentionally
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

    This is an observability helper, not a clinical gate. A value of 0 means no
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
