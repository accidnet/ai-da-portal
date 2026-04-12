import json
import logging
import re
from collections.abc import Iterable
from typing import Any, cast

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from core.config import Settings
from domain.auth.service import OpenAiAuthService
from infrastructure.llm.schemas import StructuredPrompt


logger = logging.getLogger(__name__)


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
    ) -> str:
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
            output = self._extract_stream_output(response)
        else:
            output = self._extract_output_text(self._coerce_dict(response))

        if output:
            return output
        raise LlmClientError("OpenAI returned no assistant text.")

    def generate_json(
        self, system: str, user_message: str, dataset_ids: list[str] | None = None
    ) -> dict[str, object]:
        raw = self.generate(
            system=system, user_message=user_message, dataset_ids=dataset_ids
        )
        return self._extract_json_object(raw)

    def create_response(
        self,
        *,
        input: list[dict[str, object]],
        instructions: str | None = None,
        tools: list[dict[str, object]] | None = None,
        tool_choice: str | dict[str, object] | None = None,
        previous_response_id: str | None = None,
        reasoning: dict[str, object] | None = None,
        parallel_tool_calls: bool | None = None,
        max_output_tokens: int | None = None,
    ) -> dict[str, object]:
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
        if previous_response_id:
            payload["previous_response_id"] = previous_response_id
        if reasoning:
            payload["reasoning"] = reasoning
        if parallel_tool_calls is not None:
            payload["parallel_tool_calls"] = parallel_tool_calls
        if max_output_tokens is not None and not use_oauth:
            payload["max_output_tokens"] = max_output_tokens

        response = self._responses_create(payload=payload, stream=use_oauth)
        if use_oauth:
            return self._normalize_response_payload(
                self._extract_stream_response_payload(response)
            )
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
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": user_message,
                    }
                ],
            }
        ]

    def _extract_stream_output(self, stream: object) -> str | None:
        final_response = self._get_final_response_payload(stream)
        if final_response is not None:
            output = self._extract_output_text(
                final_response, allow_raw_json_fallback=False
            )
            if output:
                self._close_stream(stream)
                return output.strip() or None

        deltas: list[str] = []
        final_text: str | None = None

        try:
            for event in cast(Iterable[object], stream):
                event_payload = self._event_to_dict(event)
                extracted = self._extract_text_from_event(event_payload)
                if extracted is None:
                    continue

                text, is_final = extracted
                if not text:
                    continue
                if is_final:
                    final_text = text
                else:
                    deltas.append(text)
        finally:
            self._close_stream(stream)

        if final_text:
            return final_text.strip() or None
        if deltas:
            return "".join(deltas).strip() or None
        return None

    def _extract_stream_response_payload(self, stream: object) -> dict[str, object]:
        final_response = self._get_final_response_payload(stream)
        if final_response is not None:
            self._close_stream(stream)
            return final_response

        try:
            for event in cast(Iterable[object], stream):
                event_payload = self._event_to_dict(event)
                if event_payload.get("type") != "response.completed":
                    continue
                response_payload = self._coerce_optional_dict(
                    event_payload.get("response")
                )
                if response_payload is not None:
                    return response_payload
        finally:
            self._close_stream(stream)

        raise LlmClientError("OpenAI returned no structured response payload.")

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

    def _event_to_dict(self, event: object) -> dict[str, object]:
        payload = self._coerce_optional_dict(event)
        if payload is not None:
            return payload

        event_type = getattr(event, "type", None)
        if isinstance(event_type, str):
            return {"type": event_type}
        return {}

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

    def _extract_text_from_event(
        self, event: dict[str, object]
    ) -> tuple[str, bool] | None:
        event_type = event.get("type")
        if event_type in {
            "response.output_text.delta",
            "message.delta",
        }:
            delta = event.get("delta") or event.get("text")
            if isinstance(delta, str) and delta:
                logger.debug(
                    "Captured SDK stream delta event=%s len=%s", event_type, len(delta)
                )
                return (delta, False)

        if event_type in {
            "response.output_text.done",
            "message.completed",
        }:
            text = event.get("text") or event.get("delta")
            if isinstance(text, str) and text:
                logger.debug(
                    "Captured SDK stream final event=%s len=%s", event_type, len(text)
                )
                return (text, True)

        if event_type == "response.completed":
            response_payload = self._coerce_optional_dict(event.get("response"))
            if response_payload is not None:
                completed = self._extract_output_text(
                    response_payload, allow_raw_json_fallback=False
                )
                if completed:
                    return (completed, True)

        message = self._coerce_optional_dict(event.get("message"))
        if message is not None:
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return (content.strip(), True)

        completed = self._extract_output_text(event)
        if completed and not completed.startswith("{"):
            return (completed, True)
        return None

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
