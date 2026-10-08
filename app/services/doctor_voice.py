"""Persona-specific Vietnamese speech profiles shared by the TTS endpoint."""
import asyncio
import importlib
import ssl
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


async def synthesize_doctor_speech(payload: DoctorSpeechRequest) -> bytes:
    configure_tts_trust()
    from edge_tts import Communicate

    async def collect() -> bytes:
        speech = Communicate(payload.text, **VOICE_PROFILES[payload.persona])
        chunks = [chunk["data"] async for chunk in speech.stream() if chunk["type"] == "audio"]
        audio = b"".join(chunks)
        if not audio:
            raise RuntimeError("Speech provider returned no audio")
        return audio

    return await asyncio.wait_for(collect(), timeout=25)
