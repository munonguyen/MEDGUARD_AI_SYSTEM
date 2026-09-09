from __future__ import annotations

from dataclasses import dataclass
import json
from time import perf_counter
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel


StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)


class ModelProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderResult:
    data: BaseModel
    response_id: str | None
    model: str
    latency_ms: int
    citations: tuple[str, ...] = ()
    search_queries: tuple[str, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cache_hit: bool = False


class StructuredModelProvider(Protocol):
    provider_name: str

    @property
    def is_configured(self) -> bool: ...

    def complete(
        self,
        *,
        stage: str,
        model: str,
        instructions: str,
        payload: dict[str, Any],
        response_model: type[StructuredOutput],
        request_id: str,
        controls: Any | None = None,
    ) -> ProviderResult: ...


class OpenAIResponsesProvider:
    """Responses adapter with strict output and independent verifier search."""

    provider_name = "openai"

    def __init__(self, *, api_key: str | None, base_url: str, timeout_seconds: int) -> None:
        self._api_key = api_key.strip() if api_key else None
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    @staticmethod
    def _output_text(body: dict[str, Any]) -> str:
        direct = body.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct
        for item in body.get("output", []):
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if isinstance(content, dict) and content.get("type") == "output_text":
                    value = content.get("text")
                    if isinstance(value, str) and value.strip():
                        return value
        raise ModelProviderError("model response did not contain structured output text")

    @staticmethod
    def _grounding(body: dict[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        citations: list[str] = []
        queries: list[str] = []
        for item in body.get("output", []):
            if not isinstance(item, dict):
                continue
            if item.get("type") == "web_search_call":
                action = item.get("action") or {}
                query = action.get("query")
                if isinstance(query, str) and query.strip():
                    queries.append(query)
                queries.extend(str(value) for value in action.get("queries", []) if value)
                for source in action.get("sources", []):
                    if isinstance(source, dict) and source.get("url"):
                        citations.append(str(source["url"]))
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict):
                    continue
                for annotation in content.get("annotations", []):
                    if isinstance(annotation, dict) and annotation.get("type") == "url_citation":
                        if annotation.get("url"):
                            citations.append(str(annotation["url"]))
        return tuple(dict.fromkeys(citations)), tuple(dict.fromkeys(queries))

    @staticmethod
    def _usage(body: dict[str, Any]) -> tuple[int, int, int]:
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        details = usage.get("input_tokens_details")
        details = details if isinstance(details, dict) else {}
        return (
            int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
            int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
            int(details.get("cached_tokens") or usage.get("cache_read_input_tokens") or 0),
        )

    def complete(
        self,
        *,
        stage: str,
        model: str,
        instructions: str,
        payload: dict[str, Any],
        response_model: type[StructuredOutput],
        request_id: str,
        controls: Any | None = None,
    ) -> ProviderResult:
        if not self._api_key:
            raise ModelProviderError("model provider is not configured")
        schema_name = f"medguard_{stage}"[:64]
        body = {
            "model": model,
            "store": False,
            "instructions": instructions,
            "input": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            "max_output_tokens": 2400 if stage == "answer" else 1600,
            "metadata": {"request_id": request_id[:64], "stage": stage[:64]},
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": response_model.model_json_schema(),
                },
                "verbosity": "low",
            },
        }
        if stage == "verifier":
            body.update(
                {
                    "tools": [{"type": "web_search", "search_context_size": "high"}],
                    "tool_choice": "required",
                    "include": ["web_search_call.action.sources"],
                    "max_tool_calls": 4,
                }
            )
        start = perf_counter()
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.post(
                    f"{self._base_url}/responses",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
            response.raise_for_status()
            response_body = response.json()
            parsed = response_model.model_validate_json(self._output_text(response_body))
            citations, queries = self._grounding(response_body)
            input_tokens, output_tokens, cached_input_tokens = self._usage(response_body)
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ModelProviderError(f"{stage} model request failed") from exc
        return ProviderResult(
            data=parsed,
            response_id=str(response_body.get("id")) if response_body.get("id") else None,
            model=str(response_body.get("model") or model),
            latency_ms=int((perf_counter() - start) * 1000),
            citations=citations,
            search_queries=queries,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
        )


class LiteLLMResponsesProvider(OpenAIResponsesProvider):
    """OpenAI-compatible LiteLLM gateway adapter for a single agent role."""

    provider_name = "llm-gateway"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str | None,
        timeout_seconds: int,
        reasoning_effort: str,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url or "http://not-configured.invalid/v1",
            timeout_seconds=timeout_seconds,
        )
        self._gateway_configured = bool(api_key and base_url)
        self._reasoning_effort = reasoning_effort

    @property
    def is_configured(self) -> bool:
        return self._gateway_configured

    def complete(
        self,
        *,
        stage: str,
        model: str,
        instructions: str,
        payload: dict[str, Any],
        response_model: type[StructuredOutput],
        request_id: str,
        controls: Any | None = None,
    ) -> ProviderResult:
        if not self.is_configured:
            raise ModelProviderError("llm gateway is not configured")
        schema_name = f"medguard_{stage}"[:64]
        max_output_tokens = controls.max_output_tokens if controls else (2400 if stage == "research" else 1800)
        metadata = (
            controls.safe_metadata(request_id, stage)
            if controls
            else {"request_id": request_id[:64], "stage": stage[:64]}
        )
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Request-Id": request_id[:128],
        }
        if controls:
            headers["x-litellm-customer-id"] = controls.end_user_scope
            headers["x-litellm-session-id"] = controls.session_scope
        body = {
            "model": model,
            "store": False,
            "instructions": instructions,
            "input": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            "max_output_tokens": max_output_tokens,
            "reasoning": {"effort": self._reasoning_effort},
            "metadata": metadata,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": response_model.model_json_schema(),
                },
                "verbosity": "low",
            },
            "tools": [{"type": "web_search", "search_context_size": "high"}],
            "tool_choice": "required",
            "include": ["web_search_call.action.sources"],
            "max_tool_calls": 4,
            "cache": controls.cache_directives() if controls else {"no-cache": True, "no-store": True},
        }
        start = perf_counter()
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.post(
                    f"{self._base_url}/responses",
                    headers=headers,
                    json=body,
                )
            response.raise_for_status()
            response_body = response.json()
            parsed = response_model.model_validate_json(self._output_text(response_body))
            citations, queries = self._grounding(response_body)
            input_tokens, output_tokens, cached_input_tokens = self._usage(response_body)
            response_headers = getattr(response, "headers", {})
            cache_hit = bool(response_headers.get("x-litellm-cache-key"))
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ModelProviderError(f"{stage} gateway request failed") from exc
        return ProviderResult(
            data=parsed,
            response_id=str(response_body.get("id")) if response_body.get("id") else None,
            model=str(response_body.get("model") or model),
            latency_ms=int((perf_counter() - start) * 1000),
            citations=citations,
            search_queries=queries,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
            cache_hit=cache_hit,
        )


class GeminiGroundedProvider:
    """Gemini Interactions adapter with Google Search grounding and JSON schema."""

    provider_name = "gemini"

    def __init__(self, *, api_key: str | None, base_url: str, timeout_seconds: int) -> None:
        self._api_key = api_key.strip() if api_key else None
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    @staticmethod
    def _interaction(body: dict[str, Any]) -> dict[str, Any]:
        nested = body.get("interaction")
        return nested if isinstance(nested, dict) else body

    @classmethod
    def _extract(cls, body: dict[str, Any]) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
        interaction = cls._interaction(body)
        direct = interaction.get("output_text")
        output_text = direct if isinstance(direct, str) else ""
        citations: list[str] = []
        queries: list[str] = []
        for step in interaction.get("steps", []):
            if not isinstance(step, dict):
                continue
            if step.get("type") == "google_search_call":
                arguments = step.get("arguments") or {}
                queries.extend(str(value) for value in arguments.get("queries", []) if value)
            if step.get("type") != "model_output":
                continue
            for content in step.get("content", []):
                if not isinstance(content, dict) or content.get("type") != "text":
                    continue
                if not output_text and isinstance(content.get("text"), str):
                    output_text = content["text"]
                for annotation in content.get("annotations", []):
                    if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
                        continue
                    if annotation.get("url"):
                        citations.append(str(annotation["url"]))
        if not output_text.strip():
            raise ModelProviderError("gemini response did not contain structured output text")
        return output_text, tuple(dict.fromkeys(citations)), tuple(dict.fromkeys(queries))

    def complete(
        self,
        *,
        stage: str,
        model: str,
        instructions: str,
        payload: dict[str, Any],
        response_model: type[StructuredOutput],
        request_id: str,
        controls: Any | None = None,
    ) -> ProviderResult:
        if not self._api_key:
            raise ModelProviderError("gemini provider is not configured")
        body = {
            "model": model,
            "input": f"{instructions}\n\nINPUT_JSON:\n{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}",
            "tools": [{"type": "google_search"}],
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": response_model.model_json_schema(),
            },
        }
        start = perf_counter()
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.post(
                    f"{self._base_url}/interactions",
                    headers={"x-goog-api-key": self._api_key, "Content-Type": "application/json"},
                    json=body,
                )
            response.raise_for_status()
            response_body = response.json()
            output_text, citations, queries = self._extract(response_body)
            parsed = response_model.model_validate_json(output_text)
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ModelProviderError(f"{stage} gemini request failed") from exc
        interaction = self._interaction(response_body)
        return ProviderResult(
            data=parsed,
            response_id=str(interaction.get("id")) if interaction.get("id") else None,
            model=str(interaction.get("model") or model),
            latency_ms=int((perf_counter() - start) * 1000),
            citations=citations,
            search_queries=queries,
        )
