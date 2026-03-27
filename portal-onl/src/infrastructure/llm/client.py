import json

import httpx

from core.config import Settings
from domain.auth.service import OpenAiAuthService
from infrastructure.llm.schemas import StructuredPrompt


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
    ) -> str | None:
        prompt = StructuredPrompt(
            system=system,
            user=user_message,
            tools=["dataset_context"] if dataset_ids else [],
        )

        if self._settings.openai_api_key:
            return f"API key mode is configured, but this scaffold currently prioritizes ChatGPT OAuth-backed Codex requests. Prompt tools: {', '.join(prompt.tools) or 'none'}."

        access_token = self._auth_service.get_access_token()
        if not access_token:
            return None

        account_id = self._auth_service.get_account_id()
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        if account_id:
            headers["ChatGPT-Account-Id"] = account_id

        payload = {
            "model": self._settings.llm_model,
            "instructions": prompt.system,
            "input": prompt.user,
        }

        client = self._http_client or httpx.Client(timeout=30.0)
        should_close = self._http_client is None
        try:
            response = client.post(
                self._settings.openai_codex_api_endpoint,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return self._extract_output_text(data)
        except (httpx.HTTPError, ValueError, KeyError):
            return None
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
                            if isinstance(item, dict) and isinstance(item.get("text"), str):
                                parts.append(item["text"].strip())
                        if parts:
                            return "\n\n".join(parts)

        raw_json = json.dumps(data)
        if raw_json and raw_json != "{}":
            return raw_json
        return None
