from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


OpenAiAuthStatus = Literal["disconnected", "pending", "connected"]


class OpenAiAuthorizeResult(BaseModel):
    """OpenAI OAuth 시작 결과를 API 계층으로 전달합니다."""

    authorization_url: str
    expires_at: datetime


class OpenAiAuthStatusResult(BaseModel):
    """OpenAI OAuth 연결 상태를 API 계층으로 전달합니다."""

    state: OpenAiAuthStatus
    connected: bool
    pending: bool
    account_email: str | None = None
    account_id: str | None = None
    expires_at: datetime | None = None
    scopes: list[str] = Field(default_factory=list)
