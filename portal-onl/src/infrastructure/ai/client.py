import json
import re
from typing import Protocol, cast

from shared.integrations.ai.contracts import (
    EasyInputMessage,
    InputItemList,
    ResponseInputText,
)
from infrastructure.ai.schemas import StructuredPrompt


class AiClientError(RuntimeError):
    pass


class AiClientTransientError(AiClientError):
    pass


class AiProvider(Protocol):
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
    ) -> object: ...

    def should_stream_generated_text(self) -> bool: ...


def coerce_optional_dict(value: object) -> dict[str, object] | None:
    # SDK/Pydantic 응답 객체를 내부 처리용 dict로 통일합니다.
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


class AiClient:
    def __init__(self, provider: AiProvider) -> None:
        self._provider = provider

    def generate(
        self, system: str, user_message: str, dataset_ids: list[str] | None = None
    ) -> object:
        prompt = StructuredPrompt(
            system=system,
            user=user_message,
            tools=["dataset_context"] if dataset_ids else [],
        )

        should_stream = self._provider.should_stream_generated_text()
        response = self._provider.create_response(
            input=self._build_input(prompt.user),
            instructions=prompt.system,
            stream=should_stream,
        )

        if should_stream:
            return response

        output = self._extract_output_text(self._coerce_dict(response))

        if output:
            return output
        raise AiClientError("OpenAI returned no assistant text.")

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
        stream: bool = False,
    ) -> object:
        response = self._provider.create_response(
            input=input,
            instructions=instructions,
            tools=tools,
            tool_choice=tool_choice,
            reasoning=reasoning,
            parallel_tool_calls=parallel_tool_calls,
            max_output_tokens=max_output_tokens,
            stream=stream,
        )
        if stream:
            return response
        return self._normalize_response_payload(self._coerce_dict(response))

    def _build_input(self, user_message: str) -> list[dict[str, object]]:
        return InputItemList(
            items=(
                EasyInputMessage(
                    role="user",
                    content=(ResponseInputText(text=user_message),),
                ),
            )
        ).to_payload()

    def _coerce_dict(self, value: object) -> dict[str, object]:
        payload = coerce_optional_dict(value)
        if payload is None:
            raise AiClientError("OpenAI JSON response was not an object.")
        return payload

    def _normalize_response_payload(
        self, response: dict[str, object]
    ) -> dict[str, object]:
        nested_response = coerce_optional_dict(response.get("response"))
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
            raise AiClientError(
                "OpenAI returned invalid JSON for structured output."
            ) from exc

        if not isinstance(payload, dict):
            raise AiClientError(
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

        nested_response = coerce_optional_dict(data.get("response"))
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
                item_payload = coerce_optional_dict(item)
                if item_payload is None:
                    continue
                content = item_payload.get("content")
                if not isinstance(content, list):
                    continue
                for entry in content:
                    entry_payload = coerce_optional_dict(entry)
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
            first_choice = coerce_optional_dict(choices[0])
            if first_choice is not None:
                message = coerce_optional_dict(first_choice.get("message"))
                if message is not None:
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()
                    if isinstance(content, list):
                        parts: list[str] = []
                        for item in content:
                            item_payload = coerce_optional_dict(item)
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
