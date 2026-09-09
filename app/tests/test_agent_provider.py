from __future__ import annotations

import json

from pydantic import BaseModel

from app.services.agent_provider import (
    GeminiGroundedProvider,
    LiteLLMResponsesProvider,
    ModelProviderError,
    OpenAIResponsesProvider,
)
from app.services.llm_control_plane import gateway_controls, policy_for_intent


class ResultSchema(BaseModel):
    approved: bool


class FakeResponse:
    def __init__(self, body: dict) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._body


class FakeClient:
    response_body: dict = {}
    last_request: dict = {}

    def __init__(self, **_values) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_values) -> None:
        return None

    def post(self, url: str, **values) -> FakeResponse:
        type(self).last_request = {"url": url, **values}
        return FakeResponse(type(self).response_body)


def test_openai_verifier_forces_independent_web_search_and_extracts_grounding(monkeypatch):
    source_url = "https://www.nice.org.uk/guidance/cg150"
    FakeClient.response_body = {
        "id": "resp_test",
        "model": "gpt-test",
        "output": [
            {
                "type": "web_search_call",
                "action": {
                    "query": "NICE headache red flags",
                    "sources": [{"url": source_url, "title": "NICE headache guidance"}],
                },
            },
            {
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps({"approved": True})}],
            },
        ],
    }
    monkeypatch.setattr("app.services.agent_provider.httpx.Client", FakeClient)
    provider = OpenAIResponsesProvider(api_key="test-key", base_url="https://api.openai.com/v1", timeout_seconds=5)

    result = provider.complete(
        stage="verifier",
        model="gpt-test",
        instructions="Verify independently.",
        payload={"draft": "test"},
        response_model=ResultSchema,
        request_id="req-provider",
    )

    request_body = FakeClient.last_request["json"]
    assert request_body["tools"] == [{"type": "web_search", "search_context_size": "high"}]
    assert request_body["tool_choice"] == "required"
    assert request_body["include"] == ["web_search_call.action.sources"]
    assert request_body["store"] is False
    assert result.citations == (source_url,)
    assert result.search_queries == ("NICE headache red flags",)


def test_gemini_extract_uses_provider_steps_not_model_authored_source_fields():
    source_url = "https://www.who.int/news-room/fact-sheets/detail/headache-disorders"
    body = {
        "interaction": {
            "output_text": json.dumps({"approved": True}),
            "steps": [
                {"type": "google_search_call", "arguments": {"queries": ["WHO headache disorders"]}},
                {
                    "type": "model_output",
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"approved": True}),
                            "annotations": [{"type": "url_citation", "url": source_url}],
                        }
                    ],
                },
            ],
        }
    }

    output, citations, queries = GeminiGroundedProvider._extract(body)

    assert json.loads(output) == {"approved": True}
    assert citations == (source_url,)
    assert queries == ("WHO headache disorders",)


def test_litellm_gateway_uses_alias_virtual_key_search_and_no_cache(monkeypatch):
    source_url = "https://www.who.int/news-room/fact-sheets/detail/headache-disorders"
    FakeClient.response_body = {
        "id": "resp_gateway",
        "model": "gateway-physical-model",
        "output": [
            {
                "type": "web_search_call",
                "action": {
                    "query": "WHO headache red flags",
                    "sources": [{"url": source_url, "title": "WHO"}],
                },
            },
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": json.dumps({"approved": True})}
                ],
            },
        ],
    }
    monkeypatch.setattr("app.services.agent_provider.httpx.Client", FakeClient)
    provider = LiteLLMResponsesProvider(
        api_key="sk-virtual-medguard",
        base_url="http://litellm:4000/v1",
        timeout_seconds=45,
        reasoning_effort="high",
    )

    result = provider.complete(
        stage="research",
        model="medguard-answer",
        instructions="Research from authoritative sources.",
        payload={"question": "dau dau"},
        response_model=ResultSchema,
        request_id="req-gateway",
    )

    request = FakeClient.last_request
    request_body = request["json"]
    assert request["url"] == "http://litellm:4000/v1/responses"
    assert request["headers"]["Authorization"] == "Bearer sk-virtual-medguard"
    assert request_body["model"] == "medguard-answer"
    assert request_body["tools"] == [
        {"type": "web_search", "search_context_size": "high"}
    ]
    assert request_body["tool_choice"] == "required"
    assert request_body["reasoning"] == {"effort": "high"}
    assert request_body["cache"] == {"no-cache": True, "no-store": True}
    assert request_body["store"] is False
    assert result.citations == (source_url,)
    assert result.search_queries == ("WHO headache red flags",)


def test_litellm_gateway_requires_url_and_virtual_key():
    missing_url = LiteLLMResponsesProvider(
        api_key="virtual-key",
        base_url=None,
        timeout_seconds=5,
        reasoning_effort="high",
    )
    missing_key = LiteLLMResponsesProvider(
        api_key=None,
        base_url="http://litellm:4000/v1",
        timeout_seconds=5,
        reasoning_effort="high",
    )

    assert missing_url.is_configured is False
    assert missing_key.is_configured is False

    try:
        missing_key.complete(
            stage="verifier",
            model="medguard-verifier",
            instructions="Verify.",
            payload={},
            response_model=ResultSchema,
            request_id="req-missing",
        )
    except ModelProviderError as exc:
        assert str(exc) == "llm gateway is not configured"
    else:
        raise AssertionError("an incomplete gateway configuration must fail closed")


def test_litellm_exact_cache_controls_are_scoped_and_usage_is_observable(monkeypatch):
    FakeClient.response_body = {
        "id": "resp_cached",
        "model": "physical-hidden",
        "output_text": json.dumps({"approved": True}),
        "usage": {
            "input_tokens": 80,
            "output_tokens": 12,
            "input_tokens_details": {"cached_tokens": 64},
        },
    }
    monkeypatch.setattr("app.services.agent_provider.httpx.Client", FakeClient)
    provider = LiteLLMResponsesProvider(
        api_key="sk-virtual-medguard",
        base_url="http://litellm:4000/v1",
        timeout_seconds=45,
        reasoning_effort="high",
    )
    controls = gateway_controls(
        role="answer",
        policy=policy_for_intent("authenticity"),
        tenant_id="secret-tenant",
        conversation_id="secret-conversation",
        locale="vi-VN",
        patient_context={},
        prompt_version="v1",
        knowledge_version="k1",
        tool_result={"status": "registry_match"},
        instructions="Research.",
        payload={"question": "QR"},
        max_input_tokens=1000,
        max_output_tokens=321,
    )

    result = provider.complete(
        stage="research",
        model="medguard-answer",
        instructions="Research.",
        payload={"question": "QR"},
        response_model=ResultSchema,
        request_id="request-visible",
        controls=controls,
    )

    request = FakeClient.last_request
    assert request["json"]["cache"]["use-cache"] is True
    assert request["json"]["max_output_tokens"] == 321
    assert request["headers"]["x-litellm-customer-id"] == controls.end_user_scope
    assert request["headers"]["x-litellm-session-id"] == controls.session_scope
    assert request["headers"]["X-Request-Id"] == "request-visible"
    assert "request_id" not in request["json"]["metadata"]
    assert "secret-tenant" not in json.dumps(request)
    assert "secret-conversation" not in json.dumps(request)
    assert result.input_tokens == 80
    assert result.output_tokens == 12
    assert result.cached_input_tokens == 64
