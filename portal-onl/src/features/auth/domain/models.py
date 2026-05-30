from datetime import datetime

from pydantic import BaseModel


class PendingOpenAiAuth(BaseModel):
    """OpenAI OAuth 완료 전 검증해야 하는 PKCE 상태입니다."""

    state: str
    code_verifier: str
    redirect_uri: str
    created_at: datetime
    expires_at: datetime


class OpenAiTokenBundle(BaseModel):
    """OpenAI OAuth 토큰과 계정 식별 정보를 함께 보관합니다."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    scope: str | None = None
    expires_at: datetime | None = None
    account_id: str | None = None
    account_email: str | None = None
    subject: str | None = None
    id_token: str | None = None


class OpenAiAuthState(BaseModel):
    """로컬 파일에 저장되는 OpenAI 인증 상태입니다."""

    pending: PendingOpenAiAuth | None = None
    connection: OpenAiTokenBundle | None = None
