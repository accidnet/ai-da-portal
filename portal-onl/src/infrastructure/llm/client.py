import json

import httpx

from core.config import Settings
from domain.auth.service import OpenAiAuthService
from infrastructure.llm.schemas import StructuredPrompt


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
            "instructions": prompt.system,
            "input": prompt.user,
        }

        return self._request_response(
            endpoint=self._settings.openai_codex_api_endpoint,
            headers=headers,
            payload=payload,
        )

    def _generate_with_api_key(self, prompt: StructuredPrompt) -> str:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._settings.llm_model,
            "instructions": prompt.system,
            "input": prompt.user,
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
            "Accept": "application/json",
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
            response = client.post(
                endpoint,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            output = self._extract_output_text(data)
            if output:
                return output
            raise LlmClientError("OpenAI returned no assistant text.")
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip() if exc.response is not None else str(exc)
            raise LlmClientError(
                f"OpenAI request failed: {detail or str(exc)}"
            ) from exc
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise LlmClientError("OpenAI response could not be processed.") from exc
        finally:
            if should_close:
                client.close()

    def _extract_output_text(self, data: dict[str, object]) -> str | None:
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

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

        raw_json = json.dumps(data)
        if raw_json and raw_json != "{}":
            return raw_json
        return None
