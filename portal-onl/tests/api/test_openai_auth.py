from datetime import UTC, datetime, timedelta

import httpx
from fastapi.testclient import TestClient

from api.deps import get_openai_auth_service
from core.config import Settings
from domain.auth.schemas import (
    OpenAiAuthState,
    OpenAiAuthStatusResponse,
    OpenAiAuthorizeResponse,
    PendingOpenAiAuth,
    OpenAiTokenBundle,
)
from domain.auth.service import OpenAiAuthError, OpenAiAuthService, OpenAiAuthStore
from main import app


class FakeOpenAiAuthService:
    def __init__(self) -> None:
        self.status = OpenAiAuthStatusResponse(
            state="disconnected",
            connected=False,
            pending=False,
        )
        self.redirect_uri: str | None = None

    def get_status(self) -> OpenAiAuthStatusResponse:
        return self.status

    def build_authorize_url(self, redirect_uri: str) -> OpenAiAuthorizeResponse:
        self.redirect_uri = redirect_uri
        assert redirect_uri.endswith("/api/v1/auth/openai/callback")
        self.status = OpenAiAuthStatusResponse(
            state="pending",
            connected=False,
            pending=True,
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        return OpenAiAuthorizeResponse(
            authorization_url="https://auth.openai.com/oauth/authorize?state=test-state",
            expires_at=self.status.expires_at,
        )

    def complete_callback(self, code: str, state_value: str) -> OpenAiTokenBundle:
        assert code == "demo-code"
        assert state_value == "demo-state"
        self.status = OpenAiAuthStatusResponse(
            state="connected",
            connected=True,
            pending=False,
            account_email="analyst@example.com",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        return OpenAiTokenBundle(
            access_token="access-token",
            refresh_token="refresh-token",
            account_email="analyst@example.com",
            expires_at=self.status.expires_at,
        )


def test_openai_auth_authorize_and_status() -> None:
    service = FakeOpenAiAuthService()
    app.dependency_overrides[get_openai_auth_service] = lambda: service

    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        initial = client.get("/api/v1/auth/openai/status")
        assert initial.status_code == 200
        assert initial.json()["state"] == "disconnected"

        authorize = client.post("/api/v1/auth/openai/authorize")
        assert authorize.status_code == 200
        assert authorize.json()["authorization_url"].startswith(
            "https://auth.openai.com/oauth/authorize"
        )

        pending = client.get("/api/v1/auth/openai/status")
        assert pending.status_code == 200
        assert pending.json()["state"] == "pending"
        assert (
            service.redirect_uri == "http://localhost:8000/api/v1/auth/openai/callback"
        )

    app.dependency_overrides.clear()


def test_openai_auth_callback_returns_success_page() -> None:
    service = FakeOpenAiAuthService()
    app.dependency_overrides[get_openai_auth_service] = lambda: service

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/auth/openai/callback",
            params={"code": "demo-code", "state": "demo-state"},
        )
        assert response.status_code == 200
        assert "ChatGPT is connected" in response.text
        assert "analyst@example.com" in response.text
        assert "portal-openai-auth" in response.text
        assert "window.opener.postMessage" in response.text

    app.dependency_overrides.clear()


class FailingTokenClient:
    def post(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise httpx.HTTPStatusError(
            "boom",
            request=httpx.Request("POST", "https://auth.openai.com/oauth/token"),
            response=httpx.Response(status_code=400),
        )


class RecordingTokenClient:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] | None = None

    def post(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        self.kwargs = kwargs
        return httpx.Response(
            status_code=200,
            request=httpx.Request("POST", "https://auth.openai.com/oauth/token"),
            json={
                "access_token": "header.payload.signature",
                "refresh_token": "refresh-token",
                "expires_in": 3600,
            },
        )


def test_openai_auth_failure_clears_pending_state(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = OpenAiAuthStore(str(tmp_path / "openai_auth.json"))
    store.save(
        OpenAiAuthState(
            pending=PendingOpenAiAuth(
                state="demo-state",
                code_verifier="demo-verifier",
                redirect_uri="http://127.0.0.1:8000/api/v1/auth/openai/callback",
                created_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
            )
        )
    )
    service = OpenAiAuthService(
        settings=Settings(),
        store=store,
        http_client=FailingTokenClient(),
    )

    try:
        service.complete_callback(code="demo-code", state_value="demo-state")
    except OpenAiAuthError:
        pass
    else:
        raise AssertionError("Expected OpenAiAuthError")

    assert store.load().pending is None


def test_openai_token_exchange_uses_form_payload(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = OpenAiAuthStore(str(tmp_path / "openai_auth.json"))
    client = RecordingTokenClient()
    service = OpenAiAuthService(
        settings=Settings(),
        store=store,
        http_client=client,
    )

    service._request_token(  # noqa: SLF001
        {
            "grant_type": "authorization_code",
            "client_id": "client-id",
            "code": "code",
            "code_verifier": "verifier",
            "redirect_uri": "http://localhost:8000/callback",
        }
    )

    assert client.kwargs is not None
    assert client.kwargs.get("data") == {
        "grant_type": "authorization_code",
        "client_id": "client-id",
        "code": "code",
        "code_verifier": "verifier",
        "redirect_uri": "http://localhost:8000/callback",
    }
    assert "json" not in client.kwargs
