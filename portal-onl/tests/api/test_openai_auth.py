from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from api.deps import get_openai_auth_service
from domain.auth.schemas import (
    OpenAiAuthStatusResponse,
    OpenAiAuthorizeResponse,
    OpenAiTokenBundle,
)
from main import app


class FakeOpenAiAuthService:
    def __init__(self) -> None:
        self.status = OpenAiAuthStatusResponse(
            state="disconnected",
            connected=False,
            pending=False,
        )

    def get_status(self) -> OpenAiAuthStatusResponse:
        return self.status

    def build_authorize_url(self, redirect_uri: str) -> OpenAiAuthorizeResponse:
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

    with TestClient(app) as client:
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

    app.dependency_overrides.clear()
