import json

import httpx
import pytest

from scripts.check_agent_release import check_release


@pytest.mark.parametrize("failure", [None, "fallback", "reviewer", "stale_dental", "readiness"])
def test_release_requires_real_stage_success_and_correct_current_topic(failure):
    turns = []
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"production_ready": failure != "readiness", "checks": []})
        body = json.loads(request.content)
        turns.append(body)
        index = len(turns)
        answer = {"narrative": [{"text": ["Gọi 115", "Khám nha sĩ vì đau răng", "Đánh giá Ngoại khoa"][index - 1]}], "answer_assurance": {"status": "verified"}}
        data = {"request_id": str(index), "verification_status": "verified", "answer_origin": "gateway_verified",
            "agent_execution": {"requested": True, "writer": "success", "reviewer": "success"},
            "result": {"urgency": ["EMERGENCY", "ROUTINE", "URGENT"][index - 1]},
            "reply": "Gọi 115" if index == 1 else "synthetic answer", "answer": answer}
        if failure == "fallback":
            data["answer_origin"] = "deterministic_fallback"
        if failure == "reviewer":
            data["agent_execution"]["reviewer"] = "not_run"
        if failure == "stale_dental" and index == 3:
            answer["narrative"][0]["text"] = "Khám nha sĩ"
        return httpx.Response(200, json=data)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = check_release(client, "https://synthetic.invalid", {})
    assert report["passed"] == (failure is None)
    assert len(turns[2]["messages"]) == 5
    assert len({turn["conversation_id"] for turn in turns}) == 1


def test_ocr_fails_closed_without_full_image_validator(monkeypatch):
    import builtins
    from app.tests.image_fixtures import VALID_PNG
    from app.services.ocr.preprocessor import preprocess_prescription_image
    original = builtins.__import__
    def without_pillow(name, *args, **kwargs):
        if name == "PIL":
            raise ImportError("synthetic unavailable validator")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", without_pillow)
    result = preprocess_prescription_image(VALID_PNG)
    assert not result.is_valid
    assert result.error_message == "image_validation_unavailable"


def test_live_checker_missing_configuration_is_not_a_pass(monkeypatch, capsys):
    from scripts.check_agent_release import main
    for key in ("MEDGUARD_API_URL", "MEDGUARD_API_KEY", "MEDGUARD_TENANT_ID", "MEDGUARD_CONSENT_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    assert main() == 2
    assert json.loads(capsys.readouterr().out)["passed"] is False


def test_live_checker_does_not_print_raw_transport_error(monkeypatch, capsys):
    from scripts import check_agent_release
    for key in ("MEDGUARD_API_URL", "MEDGUARD_API_KEY", "MEDGUARD_TENANT_ID", "MEDGUARD_CONSENT_TOKEN"):
        monkeypatch.setenv(key, "synthetic-secret")
    def failure(*args):
        raise httpx.RequestError("synthetic-secret in private provider URL")
    monkeypatch.setattr(check_agent_release, "check_release", failure)
    original_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original_client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200)), trust_env=False,
    ))
    assert check_agent_release.main() == 1
    assert "synthetic-secret" not in capsys.readouterr().out
