from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


OpenAiAuthStatus = Literal["disconnected", "pending", "connected"]


class OpenAiAuthorizeResponse(BaseModel):
    authorization_url: str
    expires_at: datetime


class OpenAiAuthStatusResponse(BaseModel):
    state: OpenAiAuthStatus
    connected: bool
    pending: bool
    account_email: str | None = None
    account_id: str | None = None
    expires_at: datetime | None = None
    scopes: list[str] = Field(default_factory=list)


class PendingOpenAiAuth(BaseModel):
    state: str
    code_verifier: str
    redirect_uri: str
    created_at: datetime
    expires_at: datetime


class OpenAiTokenBundle(BaseModel):
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
    pending: PendingOpenAiAuth | None = None
    connection: OpenAiTokenBundle | None = None
