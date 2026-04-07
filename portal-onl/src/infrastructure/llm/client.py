import json
import logging
import re

import httpx

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
    ) -> None:
        self._settings = settings
        self._auth_service = auth_service
        self._http_client = http_client

    def generate(
        self, system: str, user_message: str, dataset_ids: list[str] | None = None
    ) -> str:
        prompt = StructuredPrompt(
            system=system,
            user=user_message,
            tools=["dataset_context"] if dataset_ids else [],
        )

        if self._settings.openai_api_key:
            return self._generate_with_api_key(prompt)

        access_token = self._auth_service.get_access_token()
        if not access_token:
            raise LlmClientError(
                "No OpenAI credentials are available. Connect ChatGPT or configure OPENAI_API_KEY."
            )

        account_id = self._auth_service.get_account_id()
        headers = self._build_oauth_headers(
            access_token=access_token, account_id=account_id
        )
        payload = {
            "model": self._settings.llm_model,
            "store": False,
            "stream": True,
            "instructions": prompt.system,
            "input": self._build_input(prompt.user),
        }

        return self._request_response(
            endpoint=self._settings.openai_codex_api_endpoint,
            headers=headers,
            payload=payload,
        )

    def generate_json(
        self, system: str, user_message: str, dataset_ids: list[str] | None = None
    ) -> dict[str, object]:
        raw = self.generate(
            system=system, user_message=user_message, dataset_ids=dataset_ids
        )
        return self._extract_json_object(raw)

    def _generate_with_api_key(self, prompt: StructuredPrompt) -> str:
        headers = {
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {self._settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._settings.llm_model,
            "store": False,
            "stream": True,
            "instructions": prompt.system,
            "input": self._build_input(prompt.user),
        }

        return self._request_response(
            endpoint="https://api.openai.com/v1/responses",
            headers=headers,
            payload=payload,
        )

    def _build_oauth_headers(
        self, *, access_token: str, account_id: str | None
    ) -> dict[str, str]:
        headers = {
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        if account_id:
            headers["ChatGPT-Account-Id"] = account_id

        return headers

    def _request_response(
        self, *, endpoint: str, headers: dict[str, str], payload: dict[str, object]
    ) -> str:
        client = self._http_client or httpx.Client(timeout=30.0)
        should_close = self._http_client is None
        try:
            logger.debug(
                "Sending LLM request to %s with model %s",
                endpoint,
                payload.get("model"),
            )
            with client.stream(
                "POST",
                endpoint,
                headers=headers,
                json=payload,
            ) as response:
                logger.debug(
                    "Received LLM response status=%s content-type=%s",
                    response.status_code,
                    response.headers.get("content-type", ""),
                )
                response.raise_for_status()
                output = self._extract_streaming_or_json_response(response)
                if output:
                    return output
                raise LlmClientError("OpenAI returned no assistant text.")
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip() if exc.response is not None else str(exc)
            raise LlmClientError(
                f"OpenAI request failed: {detail or str(exc)}"
            ) from exc
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            response = exc.response if isinstance(exc, httpx.HTTPError) else None
            if response is not None:
                content_type = response.headers.get("content-type", "unknown")
                body_excerpt = response.text.strip()[:400]
                raise LlmClientError(
                    "OpenAI response could not be processed. "
                    f"content-type={content_type}; body={body_excerpt or '[empty]'}"
                ) from exc
            raise LlmClientError("OpenAI response could not be processed.") from exc
        finally:
            if should_close:
                client.close()

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

    def _extract_streaming_or_json_response(
        self, response: httpx.Response
    ) -> str | None:
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            logger.debug("Parsing event-stream response via iter_lines")
            return self._extract_stream_output_from_lines(response.iter_lines())

        raw_text = response.read().decode("utf-8", errors="replace")
        logger.debug(
            "Parsing non-event-stream response body excerpt=%r", raw_text[:300]
        )
        if not raw_text.strip():
            logger.error(
                "Empty LLM response body status=%s content-type=%s headers=%s",
                response.status_code,
                content_type,
                dict(response.headers),
            )
            raise LlmClientError(
                "OpenAI returned an empty response body. "
                f"content-type={content_type or 'unknown'}"
            )
        if self._looks_like_sse(raw_text):
            logger.debug("Detected SSE-style payload without text/event-stream header")
            return self._extract_stream_output_text(raw_text)

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.error(
                "Failed to decode non-SSE LLM response as JSON content-type=%s body_excerpt=%r",
                content_type,
                raw_text[:500],
            )
            raise exc
        return self._extract_output_text(data)

    def _looks_like_sse(self, raw_text: str) -> bool:
        lines = [line.strip() for line in raw_text.splitlines()[:12] if line.strip()]
        if not lines:
            return False

        sse_prefixes = ("data:", "event:", "id:", ":")
        return any(line.startswith(sse_prefixes) for line in lines)

    def _extract_stream_output_from_lines(self, lines: object) -> str | None:
        deltas: list[str] = []
        final_text: str | None = None

        for raw_line in lines:
            if not isinstance(raw_line, str):
                continue

            logger.debug("SSE line: %r", raw_line[:300])

            parsed = self._parse_sse_data_line(raw_line)
            if parsed is None:
                continue

            event, done = parsed
            if done:
                break

            extracted = self._extract_text_from_event(event)
            if extracted is None:
                continue

            text, is_final = extracted
            if text:
                if is_final:
                    final_text = text
                else:
                    deltas.append(text)

        if final_text:
            return final_text.strip() or None
        if deltas:
            return "".join(deltas).strip() or None
        return None

    def _extract_stream_output_text(self, stream_text: str) -> str | None:
        return self._extract_stream_output_from_lines(stream_text.splitlines())

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

    def _parse_sse_data_line(
        self, raw_line: str
    ) -> tuple[dict[str, object], bool] | None:
        line = raw_line.strip()
        if not line.startswith("data:"):
            return None

        payload = line[5:].strip()
        if not payload:
            return None
        if payload == "[DONE]":
            return ({}, True)

        try:
            event = json.loads(payload)
        except ValueError:
            return None

        if not isinstance(event, dict):
            return None

        return (event, False)

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
                    "Captured SSE delta event=%s len=%s", event_type, len(delta)
                )
                return (delta, False)

        if event_type in {
            "response.output_text.done",
            "message.completed",
        }:
            text = event.get("text") or event.get("delta")
            if isinstance(text, str) and text:
                logger.debug(
                    "Captured SSE final event=%s len=%s", event_type, len(text)
                )
                return (text, True)

        if event_type == "response.completed":
            response_payload = event.get("response")
            if isinstance(response_payload, dict):
                completed = self._extract_output_text(
                    response_payload, allow_raw_json_fallback=False
                )
                if completed:
                    logger.debug("Captured response.completed len=%s", len(completed))
                    return (completed, True)

        message = event.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                logger.debug("Captured message.content len=%s", len(content.strip()))
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

        nested_response = data.get("response")
        if isinstance(nested_response, dict):
            nested_text = self._extract_output_text(
                nested_response, allow_raw_json_fallback=False
            )
            if nested_text:
                return nested_text

        output = data.get("output")
        if isinstance(output, list):
            collected: list[str] = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if not isinstance(content, list):
                    continue
                for entry in content:
                    if not isinstance(entry, dict):
                        continue
                    text = entry.get("text")
                    if isinstance(text, str) and text.strip():
                        collected.append(text.strip())
                        continue
                    json_value = entry.get("json")
                    if isinstance(json_value, dict):
                        collected.append(json.dumps(json_value, ensure_ascii=False))
            if collected:
                return "\n\n".join(collected)

        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                message = first_choice.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()
                    if isinstance(content, list):
                        parts: list[str] = []
                        for item in content:
                            if isinstance(item, dict) and isinstance(
                                item.get("text"), str
                            ):
                                parts.append(item["text"].strip())
                        if parts:
                            return "\n\n".join(parts)

        if allow_raw_json_fallback:
            raw_json = json.dumps(data)
            if raw_json and raw_json != "{}":
                return raw_json
        return None
