"""Episode context selection for bounded clinical reasoning.

This module keeps lexical/domain signals in their intended role: they help
separate unrelated complaints, but they never determine diagnosis, urgency,
specialty, or patient-facing wording.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.risk_memory import should_start_new_episode


_CURRENT_TURN_PREFIX = "Lượt hiện tại:"


@dataclass(frozen=True)
class EpisodeContextSelection:
    text: str
    used_history: bool
    switched_episode: bool


def select_active_episode_text(raw_text: str) -> EpisodeContextSelection:
    """Return only the user statements belonging to the active complaint.

    ``chat._triage_episode_text`` serializes recent user turns as one statement
    per line and prefixes the latest turn with ``Lượt hiện tại:``.  We walk
    backwards from that latest turn and stop as soon as the adjacent pair is a
    clear complaint-domain switch.  Ambiguous/short follow-up answers remain in
    the current episode so clarification answers are not discarded.
    """
    if not raw_text or _CURRENT_TURN_PREFIX not in raw_text:
        return EpisodeContextSelection(
            text=raw_text,
            used_history=False,
            switched_episode=False,
        )

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return EpisodeContextSelection(text=raw_text, used_history=False, switched_episode=False)

    current_index = next(
        (idx for idx in range(len(lines) - 1, -1, -1) if lines[idx].startswith(_CURRENT_TURN_PREFIX)),
        None,
    )
    if current_index is None:
        return EpisodeContextSelection(text=raw_text, used_history=False, switched_episode=False)

    latest = lines[current_index][len(_CURRENT_TURN_PREFIX):].strip()
    if not latest:
        return EpisodeContextSelection(text=raw_text, used_history=False, switched_episode=False)

    selected = [latest]
    switched = False
    next_text = latest

    for prior in reversed(lines[:current_index]):
        if should_start_new_episode(next_text, prior):
            switched = True
            break
        selected.append(prior)
        next_text = prior

    selected.reverse()
    return EpisodeContextSelection(
        text="\n".join(selected),
        used_history=len(selected) > 1,
        switched_episode=switched,
    )
