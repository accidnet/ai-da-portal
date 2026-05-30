import base64
import hashlib
import html
import json
import socket
import threading
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from core.config import Settings
from .dto import (
    OpenAiAuthStatusResult,
    OpenAiAuthorizeResult,
)
from features.auth.domain.models import (
    OpenAiAuthState,
    OpenAiTokenBundle,
    PendingOpenAiAuth,
)
from features.auth.infrastructure.store import OpenAiAuthStore


class OpenAiAuthError(RuntimeError):
    """OpenAI OAuth 처리 중 복구 가능한 인증 오류입니다."""

    pass


class OpenAiAuthService:
    """OpenAI OAuth 시작, 콜백 완료, 토큰 갱신을 담당합니다."""

    def __init__(
        self,
        settings: Settings,
        store: OpenAiAuthStore,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._http_client = http_client

    def get_status(self) -> OpenAiAuthStatusResult:
        """현재 OpenAI OAuth 연결 상태를 반환합니다."""
        state = self._cleanup_expired_pending(self._store.load())
        connection = state.connection
        pending = state.pending

        if connection:
            return OpenAiAuthStatusResult(
                state="connected",
                connected=True,
                pending=False,
                account_email=connection.account_email,
                account_id=connection.account_id,
                expires_at=connection.expires_at,
                scopes=self._parse_scope(connection.scope),
            )

        if pending:
            return OpenAiAuthStatusResult(
                state="pending",
                connected=False,
                pending=True,
                expires_at=pending.expires_at,
            )

        return OpenAiAuthStatusResult(
            state="disconnected",
            connected=False,
            pending=False,
        )

    def build_authorize_url(self, redirect_uri: str) -> OpenAiAuthorizeResult:
        """PKCE 상태를 저장하고 OpenAI OAuth authorize URL을 생성합니다."""
        existing = self._cleanup_expired_pending(self._store.load())
        now = datetime.now(UTC)
        code_verifier = self._urlsafe_token(64)
        code_challenge = self._build_code_challenge(code_verifier)
        state_value = self._urlsafe_token(32)
        expires_at = now + timedelta(
            seconds=self._settings.openai_auth_pending_ttl_seconds
        )
        loopback_redirect_uri = self._settings.openai_auth_redirect_uri

        existing.pending = PendingOpenAiAuth(
            state=state_value,
            code_verifier=code_verifier,
            redirect_uri=loopback_redirect_uri,
            created_at=now,
            expires_at=expires_at,
        )
        self._store.save(existing)
        self._start_loopback_callback_server(
            expected_state=state_value,
            redirect_uri=loopback_redirect_uri,
        )

        params = {
            "response_type": "code",
            "client_id": self._settings.openai_auth_client_id,
            "redirect_uri": loopback_redirect_uri,
            "scope": self._settings.openai_auth_scope,
            "state": state_value,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "originator": self._settings.openai_auth_originator,
        }

        return OpenAiAuthorizeResult(
            authorization_url=f"{self._settings.openai_auth_issuer}/oauth/authorize?{urlencode(params)}",
            expires_at=expires_at,
        )

    def logout(self) -> OpenAiAuthStatusResult:
        """저장된 OpenAI OAuth 연결과 대기 상태를 제거합니다."""
        state = self._cleanup_expired_pending(self._store.load())
        if state.pending is None and state.connection is None:
            return OpenAiAuthStatusResult(
                state="disconnected",
                connected=False,
                pending=False,
            )

        state.pending = None
        state.connection = None
        self._store.save(state)
        return OpenAiAuthStatusResult(
            state="disconnected",
            connected=False,
            pending=False,
        )

    def complete_callback(self, code: str, state_value: str) -> OpenAiTokenBundle:
        """OAuth callback code를 토큰으로 교환하고 연결 상태를 저장합니다."""
        auth_state = self._cleanup_expired_pending(self._store.load())
        pending = auth_state.pending

        if pending is None:
            raise OpenAiAuthError("No pending OpenAI authentication flow was found.")
        if pending.state != state_value:
            raise OpenAiAuthError(
                "The returned OAuth state does not match the pending login."
            )

        try:
            token_bundle = self._exchange_code(code=code, pending=pending)
        except OpenAiAuthError:
            auth_state.pending = None
            self._store.save(auth_state)
            raise

        auth_state.pending = None
        auth_state.connection = token_bundle
        self._store.save(auth_state)
        return token_bundle

    def get_access_token(self) -> str | None:
        """LLM 요청에 사용할 access token을 반환하고 만료 시 갱신합니다."""
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
        """ChatGPT 계정 헤더에 사용할 account id를 반환합니다."""
        auth_state = self._store.load()
        if auth_state.connection is None:
            return None
        return auth_state.connection.account_id

    def _exchange_code(
        self, code: str, pending: PendingOpenAiAuth
    ) -> OpenAiTokenBundle:
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
            form_payload = {
                key: value for key, value in payload.items() if value is not None
            }
            response = client.post(
                f"{self._settings.openai_auth_issuer}/oauth/token",
                data=form_payload,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise OpenAiAuthError(f"OpenAI token exchange failed: {exc}") from exc
        finally:
            if should_close:
                client.close()

    def _build_token_bundle(
        self, token_response: dict[str, object]
    ) -> OpenAiTokenBundle:
        id_token = self._coerce_optional_str(token_response.get("id_token"))
        access_token = self._coerce_str(
            token_response.get("access_token"), "access_token"
        )
        claims = self._extract_claims(id_token=id_token, access_token=access_token)
        expires_in = token_response.get("expires_in")
        expires_at = None
        if isinstance(expires_in, int | float):
            expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))

        return OpenAiTokenBundle(
            access_token=access_token,
            refresh_token=self._coerce_optional_str(
                token_response.get("refresh_token")
            ),
            token_type=self._coerce_optional_str(token_response.get("token_type"))
            or "Bearer",
            scope=self._coerce_optional_str(token_response.get("scope")),
            expires_at=expires_at,
            account_id=self._coerce_optional_str(token_response.get("account_id"))
            or self._extract_account_id(claims),
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

    def _extract_claims(
        self, id_token: str | None, access_token: str
    ) -> dict[str, object]:
        if id_token:
            claims = self._decode_jwt_payload(id_token)
            if claims:
                return claims
        return self._decode_jwt_payload(access_token)

    def _extract_account_id(self, claims: dict[str, object]) -> str | None:
        direct = self._coerce_optional_str(claims.get("chatgpt_account_id"))
        if direct:
            return direct

        auth_claim = claims.get("https://api.openai.com/auth")
        if isinstance(auth_claim, dict):
            account_id = self._coerce_optional_str(auth_claim.get("chatgpt_account_id"))
            if account_id:
                return account_id

        organizations = claims.get("organizations")
        if isinstance(organizations, list):
            for organization in organizations:
                if isinstance(organization, dict):
                    account_id = self._coerce_optional_str(organization.get("id"))
                    if account_id:
                        return account_id

        return self._coerce_optional_str(claims.get("org_id"))

    def _start_loopback_callback_server(
        self, *, expected_state: str, redirect_uri: str
    ) -> None:
        parsed = urlparse(redirect_uri)
        host = parsed.hostname or "localhost"
        port = parsed.port
        path = parsed.path or "/"
        if port is None:
            raise OpenAiAuthError("OpenAI redirect URI must include a loopback port.")

        try:
            listener = socket.create_server((host, port))
        except OSError as exc:
            raise OpenAiAuthError(
                f"OpenAI loopback callback server could not start on {host}:{port}: {exc}"
            ) from exc

        thread = threading.Thread(
            target=self._serve_loopback_callback_once,
            kwargs={
                "listener": listener,
                "expected_state": expected_state,
                "expected_path": path,
            },
            daemon=True,
        )
        thread.start()

    def _serve_loopback_callback_once(
        self,
        *,
        listener: socket.socket,
        expected_state: str,
        expected_path: str,
    ) -> None:
        try:
            listener.settimeout(self._settings.openai_auth_pending_ttl_seconds)
            connection, _ = listener.accept()
        except OSError:
            listener.close()
            return

        with listener:
            with connection:
                response = self._handle_loopback_callback_request(
                    connection=connection,
                    expected_state=expected_state,
                    expected_path=expected_path,
                )
                try:
                    connection.sendall(response.encode("utf-8"))
                except OSError:
                    pass

    def _handle_loopback_callback_request(
        self,
        *,
        connection: socket.socket,
        expected_state: str,
        expected_path: str,
    ) -> str:
        error_response = self._build_loopback_http_response(
            title="ChatGPT Connection Failed",
            heading="ChatGPT sign-in failed",
            description="The OAuth callback request was malformed.",
            payload={
                "source": "portal-openai-auth",
                "status": "error",
                "error": "The OAuth callback request was malformed.",
            },
            status_line="HTTP/1.1 400 Bad Request",
        )

        try:
            connection.settimeout(5.0)
            request_bytes = connection.recv(4096)
        except OSError:
            return error_response

        request_lines = request_bytes.decode("utf-8", errors="ignore").splitlines()
        if not request_lines:
            return error_response

        parts = request_lines[0].split(" ")
        if len(parts) < 2:
            return error_response

        parsed = urlparse(f"http://localhost{parts[1]}")
        if parsed.path != expected_path:
            self._clear_pending_state()
            return self._build_loopback_http_response(
                title="ChatGPT Connection Failed",
                heading="ChatGPT sign-in failed",
                description="The OAuth callback path did not match the expected redirect URI.",
                payload={
                    "source": "portal-openai-auth",
                    "status": "error",
                    "error": "The OAuth callback path did not match the expected redirect URI.",
                },
                status_line="HTTP/1.1 400 Bad Request",
            )

        params = parse_qs(parsed.query)
        auth_error = params.get("error", [None])[0]
        if auth_error:
            description = params.get("error_description", [auth_error])[0] or auth_error
            self._clear_pending_state()
            return self._build_loopback_http_response(
                title="ChatGPT Connection Failed",
                heading="ChatGPT sign-in failed",
                description=description,
                payload={
                    "source": "portal-openai-auth",
                    "status": "error",
                    "error": description,
                },
                status_line="HTTP/1.1 400 Bad Request",
            )

        code = params.get("code", [None])[0]
        state_value = params.get("state", [None])[0]
        if not code or state_value != expected_state:
            self._clear_pending_state()
            return self._build_loopback_http_response(
                title="ChatGPT Connection Failed",
                heading="ChatGPT sign-in failed",
                description="The OAuth callback was missing a valid code or state.",
                payload={
                    "source": "portal-openai-auth",
                    "status": "error",
                    "error": "The OAuth callback was missing a valid code or state.",
                },
                status_line="HTTP/1.1 400 Bad Request",
            )

        try:
            token_bundle = self.complete_callback(code=code, state_value=state_value)
        except OpenAiAuthError as exc:
            return self._build_loopback_http_response(
                title="ChatGPT Connection Failed",
                heading="ChatGPT sign-in failed",
                description=str(exc),
                payload={
                    "source": "portal-openai-auth",
                    "status": "error",
                    "error": str(exc),
                },
                status_line="HTTP/1.1 400 Bad Request",
            )

        account_label = token_bundle.account_email or "your ChatGPT account"
        return self._build_loopback_http_response(
            title="ChatGPT Connected",
            heading="ChatGPT is connected",
            description=f"Authentication completed for <strong>{account_label}</strong>. You can return to the portal and start using GPT-backed responses.",
            payload={
                "source": "portal-openai-auth",
                "status": "success",
                "account_email": token_bundle.account_email or "",
            },
            status_line="HTTP/1.1 200 OK",
        )

    def _build_loopback_http_response(
        self,
        *,
        title: str,
        heading: str,
        description: str,
        payload: dict[str, str],
        status_line: str,
    ) -> str:
        payload_json = json.dumps(payload)
        html_body = f"""
<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{html.escape(title)}</title>
    <style>
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        font-family: \"Segoe UI\", system-ui, sans-serif;
        background: linear-gradient(180deg, #f4f7fb 0%, #dfe9f6 100%);
        color: #17314d;
      }}
      main {{
        width: min(92vw, 520px);
        padding: 32px;
        border-radius: 28px;
        background: rgba(255, 255, 255, 0.92);
        box-shadow: 0 24px 60px rgba(23, 49, 77, 0.14);
      }}
      h1 {{ margin: 0 0 12px; }}
      p {{ line-height: 1.7; }}
      button {{
        margin-top: 18px;
        padding: 14px 18px;
        border: 0;
        border-radius: 16px;
        color: white;
        background: #1f5ca8;
        cursor: pointer;
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>{html.escape(heading)}</h1>
      <p>{description}</p>
      <button type=\"button\" onclick=\"window.close()\">Close this window</button>
    </main>
    <script>
      const payload = {payload_json};
      try {{
        if (window.opener && !window.opener.closed) {{
          window.opener.postMessage(payload, '*');
        }}
      }} catch (error) {{
        console.error('Unable to notify opener', error);
      }}
      window.setTimeout(() => window.close(), 400);
    </script>
  </body>
</html>
""".strip()
        body_bytes = html_body.encode("utf-8")
        return (
            f"{status_line}\r\n"
            "Content-Type: text/html; charset=utf-8\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            "Connection: close\r\n\r\n"
            f"{html_body}"
        )

    def _clear_pending_state(self) -> None:
        state = self._store.load()
        if state.pending is not None:
            state.pending = None
            self._store.save(state)

    def _coerce_str(self, value: object, field_name: str) -> str:
        if not isinstance(value, str) or not value:
            raise OpenAiAuthError(
                f"OpenAI token response did not include a valid {field_name}."
            )
        return value

    def _coerce_optional_str(self, value: object) -> str | None:
        if isinstance(value, str) and value:
            return value
        return None
