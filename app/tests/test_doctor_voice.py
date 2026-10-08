import asyncio
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.doctor_voice import DoctorSpeechRequest, synthesize_doctor_speech


def test_profiles_have_distinct_voices_and_keep_full_text(monkeypatch):
    monkeypatch.setattr("app.services.doctor_voice.configure_tts_trust", lambda: None)
    seen = []
    class Speech:
        def __init__(self, text, **profile): seen.append((text, profile))
        async def stream(self):
            yield {"type": "WordBoundary", "data": "not audio"}
            yield {"type": "audio", "data": b"first"}
            yield {"type": "audio", "data": b"second"}
    monkeypatch.setitem(sys.modules, "edge_tts", SimpleNamespace(Communicate=Speech))
    text = "Nội dung cần đọc đầy đủ. " * 60
    for persona in ("dr_tuan", "dr_mai"):
        assert asyncio.run(synthesize_doctor_speech(DoctorSpeechRequest(text=text, persona=persona))) == b"firstsecond"
    assert all(t == text.strip() for t, _ in seen)
    assert seen[0][1]["voice"] == "vi-VN-NamMinhNeural"
    assert seen[1][1]["voice"] == "vi-VN-HoaiMyNeural"
    assert all(profile["rate"].startswith("-") for _, profile in seen)


def test_tts_post_returns_private_audio_and_validates_input(monkeypatch):
    async def synth(payload): return b"ID3" + payload.persona.encode()
    monkeypatch.setattr("app.api.routes.synthesize_doctor_speech", synth)
    with TestClient(app) as client:
        for persona in ("dr_tuan", "dr_mai"):
            response = client.post('/v1/tts', json={"text": "Chào bạn.", "persona": persona})
            assert response.status_code == 200
            assert response.headers['content-type'] == 'audio/mpeg'
            assert response.headers['cache-control'] == 'no-store'
            assert persona.encode() in response.content
        for body in ({"text":" "},{"text":"a"*4001},{"text":"Xin chào","persona":"unknown"}):
            assert client.post('/v1/tts',json=body).status_code == 400


def test_tts_provider_failure_is_clear_without_leaking_details(monkeypatch):
    async def fail(payload): raise RuntimeError('private upstream credential')
    monkeypatch.setattr("app.api.routes.synthesize_doctor_speech", fail)
    with TestClient(app) as client:
        response = client.post('/v1/tts',json={"text":"Chào bạn.","persona":"dr_mai"})
        assert response.status_code == 503
        assert 'credential' not in response.text


def test_voice_profiles_endpoint_and_headers_match_active_configuration(monkeypatch):
    from app.services.doctor_voice import VOICE_PROFILES, VOICE_PROFILE_REVISION
    async def synth(payload): return b"ID3sample"
    monkeypatch.setattr("app.api.routes.synthesize_doctor_speech", synth)
    with TestClient(app) as client:
        config=client.get('/v1/tts/profiles').json()
        assert config == {"revision":VOICE_PROFILE_REVISION,"profiles":VOICE_PROFILES}
        for persona,profile in config['profiles'].items():
            result=client.post('/v1/tts',json={"text":"Xin chào bạn.","persona":persona})
            assert result.headers['X-Doctor-Voice']==profile['voice']
            assert result.headers['X-Doctor-Voice-Rate']==profile['rate']
            assert result.headers['X-Doctor-Voice-Pitch']==profile['pitch']
            assert result.headers['X-Doctor-Voice-Revision']==config['revision']


def test_tts_trust_keeps_certificate_and_hostname_checks(monkeypatch):
    import ssl
    import app.services.doctor_voice as voice
    context = ssl.create_default_context()
    before = context.cert_store_stats()['x509_ca']
    monkeypatch.setattr(voice.importlib, 'import_module', lambda _: SimpleNamespace(_SSL_CTX=context))
    voice.configure_tts_trust.cache_clear()
    try:
        voice.configure_tts_trust()
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True
        assert context.cert_store_stats()['x509_ca'] >= before
    finally:
        voice.configure_tts_trust.cache_clear()


def test_tts_trust_rejects_disabled_verification(monkeypatch):
    import ssl
    import app.services.doctor_voice as voice
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    monkeypatch.setattr(voice.importlib, 'import_module', lambda _: SimpleNamespace(_SSL_CTX=context))
    voice.configure_tts_trust.cache_clear()
    try:
        with pytest.raises(RuntimeError, match='verification is required'):
            voice.configure_tts_trust()
    finally:
        voice.configure_tts_trust.cache_clear()


def test_disconnected_browser_cancels_upstream_synthesis(monkeypatch):
    from fastapi import HTTPException
    from app.api.routes import post_text_to_speech
    cancelled = []

    async def synth(payload):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(payload.persona)

    class Disconnected:
        async def is_disconnected(self):
            return True

    monkeypatch.setattr('app.api.routes.synthesize_doctor_speech', synth)
    with pytest.raises(HTTPException) as error:
        asyncio.run(post_text_to_speech(DoctorSpeechRequest(text='Xin chào.'), Disconnected()))
    assert error.value.status_code == 499
    assert cancelled == ['dr_tuan']


def test_legacy_get_speech_still_works(monkeypatch):
    async def synth(payload):
        return b'ID3sample'
    monkeypatch.setattr('app.api.routes.synthesize_doctor_speech', synth)
    with TestClient(app) as client:
        assert client.get('/v1/tts', params={'text':'Xin chào.', 'persona':'dr_mai'}).status_code == 200
