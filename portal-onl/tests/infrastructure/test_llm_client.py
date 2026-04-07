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
    def __init__(
        self,
        response_json: dict[str, object] | None = None,
        *,
        response_text: str | None = None,
        content_type: str = "application/json",
    ) -> None:
        self.response_json = response_json
        self.response_text = response_text
        self.content_type = content_type
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append({"url": url, **kwargs})
        if self.response_text is not None:
            return httpx.Response(
                status_code=200,
                request=httpx.Request("POST", url),
                text=self.response_text,
                headers={"content-type": self.content_type},
            )
        return httpx.Response(
            status_code=200,
            request=httpx.Request("POST", url),
            json=self.response_json,
            headers={"content-type": self.content_type},
        )

    def stream(self, method: str, url: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "POST"
        response = self.post(url, **kwargs)

        class _StreamContext:
            def __enter__(self_inner):
                return response

            def __exit__(self_inner, exc_type, exc, tb):
                return False

        return _StreamContext()


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
    assert http_client.calls[0]["json"]["store"] is False
    assert http_client.calls[0]["json"]["stream"] is True
    assert http_client.calls[0]["json"]["input"] == [
        {
            "role": "user",
            "content": [{"type": "input_text", "text": "user prompt"}],
        }
    ]


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
    assert http_client.calls[0]["json"]["store"] is False
    assert http_client.calls[0]["json"]["stream"] is True
    assert http_client.calls[0]["json"]["input"] == [
        {
            "role": "user",
            "content": [{"type": "input_text", "text": "user prompt"}],
        }
    ]


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


def test_llm_client_parses_streaming_response_events() -> None:
    stream_text = "\n".join(
        [
            'data: {"type":"response.output_text.delta","delta":"Hello"}',
            'data: {"type":"response.output_text.delta","delta":" world"}',
            "data: [DONE]",
        ]
    )
    http_client = RecordingHttpClient(
        response_text=stream_text,
        content_type="text/event-stream",
    )
    client = LlmClient(
        settings=Settings(openai_api_key="test-key"),
        auth_service=FakeAuthService(),
        http_client=http_client,
    )

    reply = client.generate(system="system", user_message="user prompt")

    assert reply == "Hello world"


def test_llm_client_parses_sse_even_without_event_stream_header() -> None:
    stream_text = (
        'data: {"type":"response.output_text.delta","delta":"Hello again"}\n\n'
    )
    http_client = RecordingHttpClient(
        response_text=stream_text,
        content_type="text/plain",
    )
    client = LlmClient(
        settings=Settings(openai_api_key="test-key"),
        auth_service=FakeAuthService(),
        http_client=http_client,
    )

    reply = client.generate(system="system", user_message="user prompt")

    assert reply == "Hello again"


def test_llm_client_detects_sse_when_event_line_comes_first() -> None:
    stream_text = "\n".join(
        [
            "event: response.output_text.delta",
            'data: {"type":"response.output_text.delta","delta":"Hello via event"}',
            "",
        ]
    )
    http_client = RecordingHttpClient(
        response_text=stream_text,
        content_type="text/plain",
    )
    client = LlmClient(
        settings=Settings(openai_api_key="test-key"),
        auth_service=FakeAuthService(),
        http_client=http_client,
    )

    reply = client.generate(system="system", user_message="user prompt")

    assert reply == "Hello via event"


def test_llm_client_prefers_done_text_over_response_completed_wrapper() -> None:
    stream_text = "\n".join(
        [
            "event: response.output_text.done",
            'data: {"type":"response.output_text.done","text":"실제 분석 결과입니다."}',
            "",
            "event: response.completed",
            'data: {"type":"response.completed","response":{"id":"resp_1","object":"response","output":[]}}',
            "",
            "data: [DONE]",
        ]
    )
    http_client = RecordingHttpClient(
        response_text=stream_text,
        content_type="text/plain",
    )
    client = LlmClient(
        settings=Settings(openai_api_key="test-key"),
        auth_service=FakeAuthService(),
        http_client=http_client,
    )

    reply = client.generate(system="system", user_message="user prompt")

    assert reply == "실제 분석 결과입니다."


def test_llm_client_generate_json_unwraps_nested_response_payload() -> None:
    http_client = RecordingHttpClient(
        {
            "id": "wrapper-1",
            "response": {
                "output": [
                    {
                        "content": [
                            {
                                "text": '{"template_id":"chart_focus","title":"Workspace","sections":[]}'
                            }
                        ]
                    }
                ]
            },
        }
    )
    client = LlmClient(
        settings=Settings(openai_api_key="test-key"),
        auth_service=FakeAuthService(),
        http_client=http_client,
    )

    payload = client.generate_json(system="system", user_message="user prompt")

    assert payload == {
        "template_id": "chart_focus",
        "title": "Workspace",
        "sections": [],
    }


def test_llm_client_generate_unwraps_nested_response_payload() -> None:
    http_client = RecordingHttpClient(
        {
            "id": "wrapper-1",
            "response": {
                "output": [
                    {
                        "content": [
                            {
                                "text": "실제 LLM 분석 응답입니다.",
                            }
                        ]
                    }
                ]
            },
        }
    )
    client = LlmClient(
        settings=Settings(openai_api_key="test-key"),
        auth_service=FakeAuthService(),
        http_client=http_client,
    )

    reply = client.generate(system="system", user_message="user prompt")

    assert reply == "실제 LLM 분석 응답입니다."


def test_llm_client_generate_json_reads_output_json_content() -> None:
    http_client = RecordingHttpClient(
        {
            "output": [
                {
                    "content": [
                        {
                            "json": {
                                "template_id": "chart_focus",
                                "title": "Workspace",
                                "sections": [],
                            }
                        }
                    ]
                }
            ]
        }
    )
    client = LlmClient(
        settings=Settings(openai_api_key="test-key"),
        auth_service=FakeAuthService(),
        http_client=http_client,
    )

    payload = client.generate_json(system="system", user_message="user prompt")

    assert payload == {
        "template_id": "chart_focus",
        "title": "Workspace",
        "sections": [],
    }
