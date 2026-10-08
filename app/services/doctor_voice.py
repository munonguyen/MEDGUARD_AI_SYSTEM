"""Persona-specific Vietnamese speech profiles shared by the TTS endpoint."""
import asyncio
import importlib
import ssl
import logging
import aiohttp
from time import perf_counter
from app.core.observability import metrics
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class DoctorSpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    persona: Literal["dr_tuan", "dr_mai"] = "dr_tuan"

    @field_validator("text")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Text cannot be blank")
        return value


VOICE_PROFILE_REVISION = "doctor-voices-20261008"

VOICE_PROFILES = {
    "dr_tuan": {"voice": "vi-VN-NamMinhNeural", "rate": "-8%", "pitch": "-6Hz"},
    "dr_mai": {"voice": "vi-VN-HoaiMyNeural", "rate": "-7%", "pitch": "-12Hz"},
}


@lru_cache(maxsize=1)
def configure_tts_trust() -> None:
    """Keep certifi roots and add the machine's trusted CA certificates.

    Compatibility adapter for pinned edge-tts 7.2.8, which uses its own shared
    SSL context instead of the system default. Never disable verification.
    """
    transport = importlib.import_module('edge_tts.communicate')
    context = getattr(transport, '_SSL_CTX', None)
    if not isinstance(context, ssl.SSLContext):
        raise RuntimeError('Unsupported TTS transport')
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise RuntimeError('TTS certificate verification is required')
    context.load_default_certs()


class SpeechProviderError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def speech_failure_code(error: Exception) -> str:
    if isinstance(error, (ssl.SSLCertVerificationError, aiohttp.ClientConnectorCertificateError,
                          aiohttp.ClientConnectorSSLError)):
        return 'tts_certificate_error'
    if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
        return 'tts_timeout'
    if type(error).__name__ == 'NoAudioReceived':
        return 'tts_empty_audio'
    if isinstance(error, aiohttp.ClientResponseError):
        return 'tts_provider_busy' if error.status in (429, 500, 502, 503, 504) else 'tts_provider_rejected'
    if isinstance(error, (aiohttp.ClientError, ConnectionError, OSError)):
        return 'tts_connection_error'
    return 'tts_provider_error'


async def synthesize_doctor_speech(payload: DoctorSpeechRequest) -> bytes:
    configure_tts_trust()
    from edge_tts import Communicate

    async def collect() -> bytes:
        speech = Communicate(payload.text, **VOICE_PROFILES[payload.persona])
        started = perf_counter()
        chunks = []
        async for chunk in speech.stream():
            if chunk["type"] != "audio":
                continue
            if not chunks:
                metrics.observe_histogram("medguard_tts_first_chunk_ms", (perf_counter() - started) * 1000,
                                          labels={"persona": payload.persona})
            chunks.append(chunk["data"])
        metrics.observe_histogram("medguard_tts_complete_ms", (perf_counter() - started) * 1000,
                                  labels={"persona": payload.persona})
        audio = b"".join(chunks)
        if not audio:
            raise SpeechProviderError('tts_empty_audio')
        return audio

    async def attempt() -> bytes:
        for index in range(2):
            try:
                return await collect()
            except Exception as error:
                code = error.code if isinstance(error, SpeechProviderError) else speech_failure_code(error)
                retryable = code in {'tts_empty_audio','tts_connection_error','tts_provider_busy'}
                if index == 0 and retryable:
                    await asyncio.sleep(.2)
                    continue
                raise SpeechProviderError(code) from None
    try:
        # One deadline covers both attempts, including a possible backoff.
        return await asyncio.wait_for(attempt(), timeout=25)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        code = error.code if isinstance(error, SpeechProviderError) else speech_failure_code(error)
        logging.getLogger(__name__).warning('doctor_tts_failed code=%s persona=%s', code, payload.persona)
        raise SpeechProviderError(code) from None
