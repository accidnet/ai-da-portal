import json
from typing import Any, cast

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from core.config import Settings
from domain.auth.service import OpenAiAuthService
from infrastructure.ai.client import AiClientError


class OpenAiProvider:
    def __init__(
        self,
        settings: Settings,
        auth_service: OpenAiAuthService,
        http_client: httpx.Client | None = None,
        openai_client: object | None = None,
    ) -> None:
        self._settings = settings
        self._auth_service = auth_service
        self._http_client = http_client
        self._openai_client = openai_client

    def create_response(
        self,
        *,
        input: list[dict[str, object]],
        instructions: str | None = None,
        tools: list[dict[str, object]] | None = None,
        tool_choice: str | dict[str, object] | None = None,
        reasoning: dict[str, object] | None = None,
        parallel_tool_calls: bool | None = None,
        max_output_tokens: int | None = None,
        stream: bool = False,
    ) -> object:
        payload: dict[str, object] = {
            "model": self._settings.llm_model,
            "store": False,
            "input": input,
        }
        if instructions:
            payload["instructions"] = instructions
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if reasoning:
            payload["reasoning"] = reasoning
        if parallel_tool_calls is not None:
            payload["parallel_tool_calls"] = parallel_tool_calls
        if max_output_tokens is not None and not self._uses_oauth():
            payload["max_output_tokens"] = max_output_tokens

        return self._responses_create(payload=payload, stream=stream)

    def should_stream_generated_text(self) -> bool:
        return self._uses_oauth()

    def _uses_oauth(self) -> bool:
        return not bool(self._settings.openai_api_key)

    def _get_openai_client(self) -> object:
        if self._openai_client is not None:
            return self._openai_client

        if self._settings.openai_api_key:
            self._openai_client = OpenAI(
                api_key=self._settings.openai_api_key,
                http_client=self._http_client,
            )
            return self._openai_client

        access_token = self._auth_service.get_access_token()
        if not access_token:
            raise AiClientError(
                "No OpenAI credentials are available. Connect ChatGPT or configure OPENAI_API_KEY."
            )

        account_id = self._auth_service.get_account_id()
        default_headers: dict[str, str] = {}
        if account_id:
            default_headers["ChatGPT-Account-Id"] = account_id

        self._openai_client = OpenAI(
            api_key=access_token,
            base_url=self._settings.openai_codex_api_endpoint.removesuffix(
                "/responses"
            ),
            default_headers=default_headers or None,
            http_client=self._http_client,
        )
        return self._openai_client

    def _responses_create(self, *, payload: dict[str, object], stream: bool) -> object:
        client = self._get_openai_client()
        try:
            return cast(Any, client).responses.create(**payload, stream=stream)
        except APIStatusError as exc:
            detail = self._extract_api_error_detail(exc)
            raise AiClientError(
                f"OpenAI request failed: {detail or str(exc)}"
            ) from exc
        except (APIConnectionError, APITimeoutError) as exc:
            raise AiClientError("OpenAI response could not be processed.") from exc
        except Exception as exc:  # pragma: no cover - SDK-specific fallback
            raise AiClientError("OpenAI response could not be processed.") from exc

    def _extract_api_error_detail(self, exc: APIStatusError) -> str:
        response = getattr(exc, "response", None)
        if response is None:
            return str(exc)

        data = getattr(response, "json", None)
        if callable(data):
            try:
                payload = data()
            except Exception:  # pragma: no cover - defensive logging path
                payload = None
            if payload is not None:
                return json.dumps(payload, ensure_ascii=False)

        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()

        return str(exc)
