import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import httpx

from core.config import Settings
from domain.auth.schemas import (
    OpenAiAuthState,
    OpenAiAuthStatusResponse,
    OpenAiAuthorizeResponse,
    OpenAiTokenBundle,
    PendingOpenAiAuth,
)


class OpenAiAuthError(RuntimeError):
    pass


class OpenAiAuthStore:
    def __init__(self, storage_path: str) -> None:
        self._path = Path(storage_path)

    def load(self) -> OpenAiAuthState:
        if not self._path.exists():
            return OpenAiAuthState()
        return OpenAiAuthState.model_validate_json(self._path.read_text(encoding="utf-8"))

    def save(self, state: OpenAiAuthState) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            state.model_dump_json(indent=2),
            encoding="utf-8",
        )


class OpenAiAuthService:
    def __init__(
        self,
        settings: Settings,
        store: OpenAiAuthStore,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._http_client = http_client

    def get_status(self) -> OpenAiAuthStatusResponse:
        state = self._cleanup_expired_pending(self._store.load())
        connection = state.connection
        pending = state.pending

        if connection:
            return OpenAiAuthStatusResponse(
                state="connected",
                connected=True,
                pending=False,
                account_email=connection.account_email,
                account_id=connection.account_id,
                expires_at=connection.expires_at,
                scopes=self._parse_scope(connection.scope),
            )

        if pending:
            return OpenAiAuthStatusResponse(
                state="pending",
                connected=False,
                pending=True,
                expires_at=pending.expires_at,
            )

        return OpenAiAuthStatusResponse(
            state="disconnected",
            connected=False,
            pending=False,
        )

    def build_authorize_url(self, redirect_uri: str) -> OpenAiAuthorizeResponse:
        existing = self._cleanup_expired_pending(self._store.load())
        now = datetime.now(UTC)
        code_verifier = self._urlsafe_token(64)
        code_challenge = self._build_code_challenge(code_verifier)
        state_value = self._urlsafe_token(32)
        expires_at = now + timedelta(seconds=self._settings.openai_auth_pending_ttl_seconds)

        existing.pending = PendingOpenAiAuth(
            state=state_value,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
            created_at=now,
            expires_at=expires_at,
        )
        self._store.save(existing)

        params = {
            "response_type": "code",
            "client_id": self._settings.openai_auth_client_id,
            "redirect_uri": redirect_uri,
            "scope": self._settings.openai_auth_scope,
            "state": state_value,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "originator": "portal-onl",
        }

        return OpenAiAuthorizeResponse(
            authorization_url=f"{self._settings.openai_auth_issuer}/oauth/authorize?{urlencode(params)}",
            expires_at=expires_at,
        )

    def complete_callback(self, code: str, state_value: str) -> OpenAiTokenBundle:
        auth_state = self._cleanup_expired_pending(self._store.load())
        pending = auth_state.pending

        if pending is None:
            raise OpenAiAuthError("No pending OpenAI authentication flow was found.")
        if pending.state != state_value:
            raise OpenAiAuthError("The returned OAuth state does not match the pending login.")

        token_bundle = self._exchange_code(code=code, pending=pending)
        auth_state.pending = None
        auth_state.connection = token_bundle
        self._store.save(auth_state)
        return token_bundle

    def get_access_token(self) -> str | None:
        auth_state = self._store.load()
        connection = auth_state.connection
        if connection is None:
            return None

        if self._is_expired(connection) and connection.refresh_token:
            refreshed = self._refresh_token(connection)
            auth_state.connection = refreshed
            self._store.save(auth_state)
            connection = refreshed

        if self._is_expired(connection):
            return None

        return connection.access_token

    def get_account_id(self) -> str | None:
        auth_state = self._store.load()
        if auth_state.connection is None:
            return None
        return auth_state.connection.account_id

    def _exchange_code(self, code: str, pending: PendingOpenAiAuth) -> OpenAiTokenBundle:
        payload = {
            "grant_type": "authorization_code",
            "client_id": self._settings.openai_auth_client_id,
            "code": code,
            "code_verifier": pending.code_verifier,
            "redirect_uri": pending.redirect_uri,
        }
        response = self._request_token(payload)
        return self._build_token_bundle(response)

    def _refresh_token(self, connection: OpenAiTokenBundle) -> OpenAiTokenBundle:
        payload = {
            "grant_type": "refresh_token",
            "client_id": self._settings.openai_auth_client_id,
            "refresh_token": connection.refresh_token,
        }
        response = self._request_token(payload)
        refreshed = self._build_token_bundle(response)
        if refreshed.account_email is None:
            refreshed.account_email = connection.account_email
        if refreshed.account_id is None:
            refreshed.account_id = connection.account_id
        if refreshed.subject is None:
            refreshed.subject = connection.subject
        return refreshed

    def _request_token(self, payload: dict[str, str | None]) -> dict[str, object]:
        client = self._http_client or httpx.Client(timeout=20.0)
        should_close = self._http_client is None
        try:
            response = client.post(
                f"{self._settings.openai_auth_issuer}/oauth/token",
                json=payload,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise OpenAiAuthError(f"OpenAI token exchange failed: {exc}") from exc
        finally:
            if should_close:
                client.close()

    def _build_token_bundle(self, token_response: dict[str, object]) -> OpenAiTokenBundle:
        id_token = self._coerce_optional_str(token_response.get("id_token"))
        claims = self._decode_jwt_payload(id_token) if id_token else {}
        expires_in = token_response.get("expires_in")
        expires_at = None
        if isinstance(expires_in, int | float):
            expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))

        return OpenAiTokenBundle(
            access_token=self._coerce_str(token_response.get("access_token"), "access_token"),
            refresh_token=self._coerce_optional_str(token_response.get("refresh_token")),
            token_type=self._coerce_optional_str(token_response.get("token_type")) or "Bearer",
            scope=self._coerce_optional_str(token_response.get("scope")),
            expires_at=expires_at,
            account_id=self._coerce_optional_str(token_response.get("account_id"))
            or self._coerce_optional_str(claims.get("org_id")),
            account_email=self._coerce_optional_str(claims.get("email")),
            subject=self._coerce_optional_str(claims.get("sub")),
            id_token=id_token,
        )

    def _cleanup_expired_pending(self, state: OpenAiAuthState) -> OpenAiAuthState:
        if state.pending and state.pending.expires_at <= datetime.now(UTC):
            state.pending = None
            self._store.save(state)
        return state

    def _is_expired(self, bundle: OpenAiTokenBundle) -> bool:
        if bundle.expires_at is None:
            return False
        return bundle.expires_at <= datetime.now(UTC) + timedelta(seconds=30)

    def _parse_scope(self, scope: str | None) -> list[str]:
        if not scope:
            return []
        return [item for item in scope.split(" ") if item]

    def _build_code_challenge(self, code_verifier: str) -> str:
        digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

    def _urlsafe_token(self, length: int) -> str:
        return secrets.token_urlsafe(length)

    def _decode_jwt_payload(self, token: str) -> dict[str, object]:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        try:
            decoded = base64.urlsafe_b64decode(payload.encode("utf-8"))
            parsed = json.loads(decoded.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            return {}
        if isinstance(parsed, dict):
            return parsed
        return {}

    def _coerce_str(self, value: object, field_name: str) -> str:
        if not isinstance(value, str) or not value:
            raise OpenAiAuthError(f"OpenAI token response did not include a valid {field_name}.")
        return value

    def _coerce_optional_str(self, value: object) -> str | None:
        if isinstance(value, str) and value:
            return value
        return None
