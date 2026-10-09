"""Request-scoped speculative speech. Draft audio is never publicly released.

The Writer starts a bounded task while the Reviewer checks the draft. After all
gates, only an exact final prefix may receive a short-lived, tenant-bound ticket.
Neither tickets nor audio are stored in history or idempotency records.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import ContextVar
from dataclasses import dataclass
import re
import secrets
from threading import BoundedSemaphore, Lock, Timer
from time import monotonic

from app.services.doctor_voice import DoctorSpeechRequest, synthesize_doctor_speech

_workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="prepared-speech")
_slots = BoundedSemaphore(2)
_active: ContextVar[VoicePreparation | None] = ContextVar("companion_voice", default=None)
_tickets: dict[str, SpeechTicket] = {}
_tickets_lock = Lock()
_TTL = 45
_MAX_AUDIO_BYTES = 256 * 1024


def plain_speech(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?m)^\s*(?:#{1,6}\s+|[-*]\s+)", "", text)
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).strip()


def first_segment(text: str, limit: int = 180) -> str:
    clean = plain_speech(text)
    boundary = re.search(r"[.!?](?=\s|$)", clean)
    end = boundary.end() if boundary else len(clean)
    if end > limit:
        space = clean.rfind(" ", 0, limit + 1)
        end = space if space > 0 else limit
    return clean[:end].strip()


def spoken_reply(response) -> str:
    """One canonical answer; preserve mandatory actions and warnings.

    Only normalized literal containment removes repeats. No fuzzy summary or
    fixed character cut is allowed to remove a clinically important sentence.
    """
    answer = response.answer
    narrative = [b.text for b in answer.narrative] if answer else []
    base = " ".join(narrative) if response.verification_status == "verified" and narrative else response.reply
    parts = [plain_speech(base)] if base else []
    if answer:
        questions = answer.display_questions if answer.display_questions is not None else answer.questions
        for value in [*answer.next_steps, *answer.safety_notes, *(questions or [])]:
            text = plain_speech(value)
            if text and not any(text.casefold() in part.casefold() for part in parts):
                parts.append(text)
    return " ".join(parts)


@dataclass
class SpeechTicket:
    tenant: str
    text: str
    persona: str
    future: Future
    expires: float


def _expire(ticket: str) -> None:
    with _tickets_lock:
        _tickets.pop(ticket, None)


def claim_speech(ticket: str, tenant: str) -> SpeechTicket | None:
    with _tickets_lock:
        entry = _tickets.get(ticket)
        if entry is None or entry.tenant != tenant:
            return None
        _tickets.pop(ticket, None)
        return entry if entry.expires > monotonic() else None


class VoicePreparation:
    def __init__(self, persona: str):
        self.persona = persona
        self.text = ""
        self.future: Future | None = None
        self.closed = False
        self.lock = Lock()

    def start(self, draft: str) -> None:
        with self.lock:
            text = first_segment(draft)
            if self.closed or self.future is not None or not text or not _slots.acquire(blocking=False):
                return
            self.text = text

            def render():
                try:
                    audio = asyncio.run(synthesize_doctor_speech(DoctorSpeechRequest(text=text, persona=self.persona)))
                    if len(audio) > _MAX_AUDIO_BYTES:
                        raise ValueError("Prepared audio exceeds bound")
                    return audio
                finally:
                    _slots.release()

            try:
                self.future = _workers.submit(render)
            except Exception:
                _slots.release()
                self.text = ""

    def approve(self, response, tenant: str) -> dict | None:
        with self.lock:
            self.closed = True
            # Final safety/grounding gates have already run in orchestrate_chat.
            if (response.verification_status != "verified" or self.future is None or
                    self.text != first_segment(response.spoken_reply or "")):
                return None
            if self.future.done() and self.future.exception() is not None:
                return None
            token = secrets.token_urlsafe(24)
            entry = SpeechTicket(tenant, self.text, self.persona, self.future, monotonic() + _TTL)
            with _tickets_lock:
                if len(_tickets) >= 32:
                    return None
                _tickets[token] = entry
            timer = Timer(_TTL, _expire, args=(token,))
            timer.daemon = True
            timer.start()
            return {"ticket": token, "text": self.text, "persona": self.persona}

    def close(self) -> None:
        with self.lock:
            self.closed = True
        # Do not cancel queued futures: render's finally owns semaphore release.
        # The provider's existing 25s deadline bounds abandoned work.


def prepare_writer_voice(text: str) -> None:
    active = _active.get()
    if active is not None:
        active.start(text)


def begin_voice(persona: str):
    preparation = VoicePreparation(persona)
    return preparation, _active.set(preparation)


def end_voice(preparation: VoicePreparation, token) -> None:
    preparation.close()
    _active.reset(token)
