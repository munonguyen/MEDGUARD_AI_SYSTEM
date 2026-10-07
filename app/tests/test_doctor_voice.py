import asyncio
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.doctor_voice import DoctorSpeechRequest, synthesize_doctor_speech


def test_profiles_have_distinct_voices_and_keep_full_text(monkeypatch):
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
