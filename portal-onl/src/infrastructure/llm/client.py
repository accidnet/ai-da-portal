import json
import re
from typing import Any, cast

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from core.config import Settings
from domain.auth.service import OpenAiAuthService
from infrastructure.llm.input_models import (
    EasyInputMessage,
    InputItemList,
    ResponseInputText,
)
from infrastructure.llm.schemas import StructuredPrompt
class LlmClientError(RuntimeError):
    pass


class LlmClient:
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

    def generate(
        self, system: str, user_message: str, dataset_ids: list[str] | None = None
    ) -> object:
        prompt = StructuredPrompt(
            system=system,
            user=user_message,
            tools=["dataset_context"] if dataset_ids else [],
        )
        payload = {
            "model": self._settings.llm_model,
            "store": False,
            "input": self._build_input(prompt.user),
            "instructions": prompt.system,
        }

        response = self._responses_create(payload=payload, stream=self._uses_oauth())

        if self._uses_oauth():
            return response

        output = self._extract_output_text(self._coerce_dict(response))

        if output:
            return output
        raise LlmClientError("OpenAI returned no assistant text.")

    def generate_json(
        self, system: str, user_message: str, dataset_ids: list[str] | None = None
    ) -> object:
        raw = self.generate(
            system=system, user_message=user_message, dataset_ids=dataset_ids
        )
        if isinstance(raw, str):
            return self._extract_json_object(raw)
        return raw

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
    ) -> object:
        use_oauth = self._uses_oauth()
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
        if max_output_tokens is not None and not use_oauth:
            payload["max_output_tokens"] = max_output_tokens

        response = self._responses_create(payload=payload, stream=use_oauth)
        if use_oauth:
            return response
        return self._normalize_response_payload(self._coerce_dict(response))

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
            raise LlmClientError(
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
            raise LlmClientError(
                f"OpenAI request failed: {detail or str(exc)}"
            ) from exc
        except (APIConnectionError, APITimeoutError) as exc:
            raise LlmClientError("OpenAI response could not be processed.") from exc
        except Exception as exc:  # pragma: no cover - SDK-specific fallback
            raise LlmClientError("OpenAI response could not be processed.") from exc

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

    def _build_input(self, user_message: str) -> list[dict[str, object]]:
        return InputItemList(
            items=(
                EasyInputMessage(
                    role="user",
                    content=(ResponseInputText(text=user_message),),
                ),
            )
        ).to_payload()

    def _get_final_response_payload(self, stream: object) -> dict[str, object] | None:
        get_final_response = getattr(stream, "get_final_response", None)
        if not callable(get_final_response):
            return None

        try:
            final_response = get_final_response()
        except Exception:
            return None
        return self._coerce_optional_dict(final_response)

    def _close_stream(self, stream: object) -> None:
        close = getattr(stream, "close", None)
        if callable(close):
            close()

    def _coerce_dict(self, value: object) -> dict[str, object]:
        payload = self._coerce_optional_dict(value)
        if payload is None:
            raise LlmClientError("OpenAI JSON response was not an object.")
        return payload

    def _coerce_optional_dict(self, value: object) -> dict[str, object] | None:
        if isinstance(value, dict):
            return cast(dict[str, object], value)

        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump(mode="python")
            if isinstance(dumped, dict):
                return cast(dict[str, object], dumped)

        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            dumped = to_dict()
            if isinstance(dumped, dict):
                return cast(dict[str, object], dumped)

        return None

    def _normalize_response_payload(
        self, response: dict[str, object]
    ) -> dict[str, object]:
        nested_response = self._coerce_optional_dict(response.get("response"))
        normalized = nested_response if nested_response is not None else dict(response)

        output_text = normalized.get("output_text")
        if not isinstance(output_text, str) or not output_text.strip():
            extracted = self._extract_output_text(
                normalized, allow_raw_json_fallback=False
            )
            if extracted:
                normalized["output_text"] = extracted

        return normalized

    def _extract_json_object(self, raw_text: str) -> dict[str, object]:
        normalized = raw_text.strip()
        fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", normalized, re.DOTALL)
        if fence_match:
            normalized = fence_match.group(1).strip()
        elif not normalized.startswith("{"):
            start = normalized.find("{")
            end = normalized.rfind("}")
            if start >= 0 and end > start:
                normalized = normalized[start : end + 1]

        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError as exc:
            raise LlmClientError(
                "OpenAI returned invalid JSON for structured output."
            ) from exc

        if not isinstance(payload, dict):
            raise LlmClientError(
                "OpenAI returned non-object JSON for structured output."
            )

        nested_response = payload.get("response")
        if isinstance(nested_response, dict):
            extracted = self._extract_output_text(
                nested_response, allow_raw_json_fallback=False
            )
            if extracted:
                return self._extract_json_object(extracted)

        extracted = self._extract_output_text(payload, allow_raw_json_fallback=False)
        if extracted and extracted != normalized:
            return self._extract_json_object(extracted)

        return payload

    def _extract_output_text(
        self, data: dict[str, object], *, allow_raw_json_fallback: bool = True
    ) -> str | None:
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        nested_response = self._coerce_optional_dict(data.get("response"))
        if nested_response is not None:
            nested_text = self._extract_output_text(
                nested_response, allow_raw_json_fallback=False
            )
            if nested_text:
                return nested_text

        output = data.get("output")
        if isinstance(output, list):
            collected: list[str] = []
            for item in output:
                item_payload = self._coerce_optional_dict(item)
                if item_payload is None:
                    continue
                content = item_payload.get("content")
                if not isinstance(content, list):
                    continue
                for entry in content:
                    entry_payload = self._coerce_optional_dict(entry)
                    if entry_payload is None:
                        continue
                    text = entry_payload.get("text")
                    if isinstance(text, str) and text.strip():
                        collected.append(text.strip())
                        continue
                    json_value = entry_payload.get("json")
                    if isinstance(json_value, dict):
                        collected.append(json.dumps(json_value, ensure_ascii=False))
            if collected:
                return "\n\n".join(collected)

        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = self._coerce_optional_dict(choices[0])
            if first_choice is not None:
                message = self._coerce_optional_dict(first_choice.get("message"))
                if message is not None:
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()
                    if isinstance(content, list):
                        parts: list[str] = []
                        for item in content:
                            item_payload = self._coerce_optional_dict(item)
                            if item_payload is None:
                                continue
                            text = item_payload.get("text")
                            if isinstance(text, str) and text.strip():
                                parts.append(text.strip())
                        if parts:
                            return "\n\n".join(parts)

        if allow_raw_json_fallback:
            raw_json = json.dumps(data)
            if raw_json and raw_json != "{}":
                return raw_json
        return None
