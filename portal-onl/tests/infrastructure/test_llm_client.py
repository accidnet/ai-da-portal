import httpx

from core.config import Settings
from infrastructure.llm.client import LlmClient, LlmClientError


class FakeAuthService:
    def __init__(
        self, access_token: str | None = None, account_id: str | None = None
    ) -> None:
        self._access_token = access_token
        self._account_id = account_id

    def get_access_token(self) -> str | None:
        return self._access_token

    def get_account_id(self) -> str | None:
        return self._account_id


class RecordingHttpClient:
    def __init__(self, response_json: dict[str, object]) -> None:
        self.response_json = response_json
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append({"url": url, **kwargs})
        return httpx.Response(
            status_code=200,
            request=httpx.Request("POST", url),
            json=self.response_json,
        )


def test_llm_client_uses_responses_api_when_api_key_is_configured() -> None:
    http_client = RecordingHttpClient({"output_text": "hello from api key"})
    client = LlmClient(
        settings=Settings(openai_api_key="test-key"),
        auth_service=FakeAuthService(),
        http_client=http_client,
    )

    reply = client.generate(system="system", user_message="user prompt")

    assert reply == "hello from api key"
    assert http_client.calls[0]["url"] == "https://api.openai.com/v1/responses"
    assert http_client.calls[0]["headers"]["Authorization"] == "Bearer test-key"


def test_llm_client_uses_chatgpt_oauth_token_when_available() -> None:
    http_client = RecordingHttpClient({"output_text": "hello from oauth"})
    client = LlmClient(
        settings=Settings(),
        auth_service=FakeAuthService(access_token="oauth-token", account_id="acct-123"),
        http_client=http_client,
    )

    reply = client.generate(
        system="system", user_message="user prompt", dataset_ids=["dataset-1"]
    )

    assert reply == "hello from oauth"
    assert http_client.calls[0]["url"] == Settings().openai_codex_api_endpoint
    assert http_client.calls[0]["headers"]["Authorization"] == "Bearer oauth-token"
    assert http_client.calls[0]["headers"]["ChatGPT-Account-Id"] == "acct-123"


def test_llm_client_raises_when_no_credentials_are_available() -> None:
    client = LlmClient(
        settings=Settings(),
        auth_service=FakeAuthService(),
    )

    try:
        client.generate(system="system", user_message="user prompt")
    except LlmClientError as exc:
        assert "No OpenAI credentials" in str(exc)
    else:
        raise AssertionError("Expected LlmClientError")
