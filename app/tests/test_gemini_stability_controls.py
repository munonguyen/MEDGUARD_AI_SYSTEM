from email.message import Message
import urllib.error

import pytest

from scripts import test_gemini_stability as stability


def test_retry_after_numeric_header_is_respected():
    headers = Message()
    headers["Retry-After"] = "12"
    error = urllib.error.HTTPError("https://provider.invalid", 429, "throttled", headers, None)
    assert stability._retry_delay(error, 1) == 12
    headers.replace_header("Retry-After", "invalid")
    assert stability._retry_delay(error, 1) == 2


def test_pacer_shares_interval_between_calls(monkeypatch):
    clock = [100.0]
    waits = []
    monkeypatch.setattr(stability.time, "monotonic", lambda: clock[0])
    def sleep(delay):
        waits.append(delay)
        clock[0] += delay
    monkeypatch.setattr(stability.time, "sleep", sleep)
    pacer = stability.RequestPacer(12)
    pacer.wait()
    clock[0] += 1
    pacer.wait()
    clock[0] += 4
    pacer.wait()
    assert waits == [11, 8]


def test_direct_stability_rejects_nonempty_wrong_output(monkeypatch):
    monkeypatch.setattr(stability, "_request_json", lambda *args, **kwargs: (
        200, {"candidates": [{"content": {"parts": [{"text": "Wrong output"}]}}]},
    ))
    with pytest.raises(RuntimeError):
        stability._direct_once("test-model", "test-key", 1)


def test_gateway_stability_accepts_exact_marker(monkeypatch):
    monkeypatch.setattr(stability, "_request_json", lambda *args, **kwargs: (
        200, {"choices": [{"message": {"content": "STABLE_OK"}}]},
    ))
    assert "HTTP 200" in stability._gateway_once("test", "test", "https://provider.invalid", 1)
