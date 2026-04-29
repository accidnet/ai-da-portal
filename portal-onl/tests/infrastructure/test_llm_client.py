from typing import Any

import pytest

from core.config import Settings
from infrastructure.ai import client as llm_client_module
from infrastructure.ai.client import AiClient, AiClientError


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


class FakeModel:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def model_dump(self, mode: str = "python") -> dict[str, object]:
        assert mode == "python"
        return self._payload


class FakeStream:
    def __init__(
        self, events: list[object], final_response: dict[str, object] | None = None
    ) -> None:
        self._events = events
        self._final_response = final_response
        self.closed = False

    def __iter__(self):
        return iter(self._events)

    def close(self) -> None:
        self.closed = True

    def get_final_response(self) -> FakeModel:
        if self._final_response is None:
            raise RuntimeError("final response is not configured")
        return FakeModel(self._final_response)


class FakeResponsesApi:
    def __init__(
        self,
        *,
        response_payload: dict[str, object] | None = None,
        stream_events: list[object] | None = None,
        stream_final_response: dict[str, object] | None = None,
    ) -> None:
        self.response_payload = response_payload or {}
        self.stream_events = stream_events or []
        self.stream_final_response = stream_final_response
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return FakeStream(self.stream_events, self.stream_final_response)
        return FakeModel(self.response_payload)


class FakeOpenAIClient:
    def __init__(self, responses_api: FakeResponsesApi) -> None:
        self.responses = responses_api


class RecordingOpenAIFactory:
    def __init__(self, client: FakeOpenAIClient) -> None:
        self._client = client
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs: Any) -> FakeOpenAIClient:
        self.calls.append(kwargs)
        return self._client


def test_llm_client_uses_responses_api_when_api_key_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk_client = FakeOpenAIClient(
        FakeResponsesApi(response_payload={"output_text": "hello from api key"})
    )
    factory = RecordingOpenAIFactory(sdk_client)
    monkeypatch.setattr(llm_client_module, "OpenAI", factory)

    client = AiClient(
        settings=Settings(openai_api_key="test-key"),
        auth_service=FakeAuthService(),
    )

    reply = client.generate(system="system", user_message="user prompt")

    assert reply == "hello from api key"
    assert factory.calls[0]["api_key"] == "test-key"
    assert sdk_client.responses.calls[0]["stream"] is False
    assert sdk_client.responses.calls[0]["store"] is False
    assert sdk_client.responses.calls[0]["input"] == [
        {
            "type": "message",
            "role": "user",
            "phase": None,
            "content": [{"type": "input_text", "text": "user prompt"}],
        }
    ]


def test_llm_client_uses_chatgpt_oauth_token_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk_client = FakeOpenAIClient(
        FakeResponsesApi(
            stream_events=[
                {"type": "response.output_text.delta", "delta": "hello"},
                {"type": "response.output_text.delta", "delta": " from oauth"},
            ]
        )
    )
    factory = RecordingOpenAIFactory(sdk_client)
    monkeypatch.setattr(llm_client_module, "OpenAI", factory)

    client = AiClient(
        settings=Settings(),
        auth_service=FakeAuthService(access_token="oauth-token", account_id="acct-123"),
    )

    reply = client.generate(
        system="system", user_message="user prompt", dataset_ids=["dataset-1"]
    )

    assert isinstance(reply, FakeStream)
    assert factory.calls[0]["api_key"] == "oauth-token"
    assert factory.calls[0]["base_url"] == "https://chatgpt.com/backend-api/codex"
    assert factory.calls[0]["default_headers"] == {"ChatGPT-Account-Id": "acct-123"}
    assert sdk_client.responses.calls[0]["stream"] is True


def test_llm_client_raises_when_no_credentials_are_available() -> None:
    client = AiClient(
        settings=Settings(),
        auth_service=FakeAuthService(),
    )

    with pytest.raises(AiClientError, match="No OpenAI credentials"):
        client.generate(system="system", user_message="user prompt")


def test_llm_client_generate_returns_stream_for_oauth() -> None:
    sdk_client = FakeOpenAIClient(
        FakeResponsesApi(
            stream_events=[
                {"type": "response.output_text.delta", "delta": "Hello"},
                {"type": "response.output_text.delta", "delta": " world"},
            ]
        )
    )
    client = AiClient(
        settings=Settings(),
        auth_service=FakeAuthService(access_token="oauth-token"),
        openai_client=sdk_client,
    )

    reply = client.generate(system="system", user_message="user prompt")

    assert isinstance(reply, FakeStream)


def test_llm_client_generate_preserves_stream_events_for_oauth() -> None:
    sdk_client = FakeOpenAIClient(
        FakeResponsesApi(
            stream_events=[
                {
                    "type": "response.output_text.done",
                    "text": "실제 분석 결과입니다.",
                },
                {
                    "type": "response.completed",
                    "response": {"id": "resp_1", "output": []},
                },
            ]
        )
    )
    client = AiClient(
        settings=Settings(),
        auth_service=FakeAuthService(access_token="oauth-token"),
        openai_client=sdk_client,
    )

    reply = client.generate(system="system", user_message="user prompt")

    assert isinstance(reply, FakeStream)


def test_llm_client_generate_json_unwraps_nested_response_payload() -> None:
    sdk_client = FakeOpenAIClient(
        FakeResponsesApi(
            response_payload={
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
    )
    client = AiClient(
        settings=Settings(openai_api_key="test-key"),
        auth_service=FakeAuthService(),
        openai_client=sdk_client,
    )

    payload = client.generate_json(system="system", user_message="user prompt")

    assert payload == {
        "template_id": "chart_focus",
        "title": "Workspace",
        "sections": [],
    }


def test_llm_client_generate_unwraps_nested_response_payload() -> None:
    sdk_client = FakeOpenAIClient(
        FakeResponsesApi(
            response_payload={
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
    )
    client = AiClient(
        settings=Settings(openai_api_key="test-key"),
        auth_service=FakeAuthService(),
        openai_client=sdk_client,
    )

    reply = client.generate(system="system", user_message="user prompt")

    assert reply == "실제 LLM 분석 응답입니다."


def test_llm_client_generate_json_reads_output_json_content() -> None:
    sdk_client = FakeOpenAIClient(
        FakeResponsesApi(
            response_payload={
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
    )
    client = AiClient(
        settings=Settings(openai_api_key="test-key"),
        auth_service=FakeAuthService(),
        openai_client=sdk_client,
    )

    payload = client.generate_json(system="system", user_message="user prompt")

    assert payload == {
        "template_id": "chart_focus",
        "title": "Workspace",
        "sections": [],
    }


def test_llm_client_create_response_sends_responses_api_tool_payload() -> None:
    responses_api = FakeResponsesApi(
        response_payload={
            "id": "resp_123",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "ok"}],
                }
            ],
        }
    )
    sdk_client = FakeOpenAIClient(responses_api)
    client = AiClient(
        settings=Settings(openai_api_key="test-key"),
        auth_service=FakeAuthService(),
        openai_client=sdk_client,
    )

    payload = client.create_response(
        instructions="system",
        input=[
            {
                "role": "user",
                "content": [{"type": "input_text", "text": "분석해줘"}],
            }
        ],
        tools=[{"type": "function", "name": "run_portal_analysis"}],
        tool_choice="auto",
        reasoning={"effort": "medium"},
        parallel_tool_calls=False,
        max_output_tokens=900,
    )

    assert payload["id"] == "resp_123"
    assert responses_api.calls[0]["stream"] is False
    assert responses_api.calls[0]["tool_choice"] == "auto"
    assert responses_api.calls[0]["parallel_tool_calls"] is False


def test_llm_client_create_response_unwraps_nested_response_payload() -> None:
    responses_api = FakeResponsesApi(
        response_payload={
            "id": "wrapper-1",
            "response": {
                "id": "resp_123",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "ok"}],
                    }
                ],
            },
        }
    )
    sdk_client = FakeOpenAIClient(responses_api)
    client = AiClient(
        settings=Settings(openai_api_key="test-key"),
        auth_service=FakeAuthService(),
        openai_client=sdk_client,
    )

    payload = client.create_response(
        input=[
            {
                "role": "user",
                "content": [{"type": "input_text", "text": "분석해줘"}],
            }
        ]
    )

    assert payload["id"] == "resp_123"
    assert payload["output_text"] == "ok"


def test_llm_client_create_response_uses_streaming_for_oauth_codex() -> None:
    responses_api = FakeResponsesApi(
        stream_events=[],
        stream_final_response={
            "id": "resp_123",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "ok"}],
                }
            ],
        },
    )
    sdk_client = FakeOpenAIClient(responses_api)
    client = AiClient(
        settings=Settings(),
        auth_service=FakeAuthService(access_token="oauth-token", account_id="acct-123"),
        openai_client=sdk_client,
    )

    payload = client.create_response(
        instructions="system",
        input=[
            {
                "role": "user",
                "content": [{"type": "input_text", "text": "분석해줘"}],
            }
        ],
    )

    assert isinstance(payload, FakeStream)
    assert responses_api.calls[0]["stream"] is True
    assert "max_output_tokens" not in responses_api.calls[0]
