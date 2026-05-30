from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


OpenAiAuthStatus = Literal["disconnected", "pending", "connected"]


class OpenAiAuthorizeResponse(BaseModel):
    """OpenAI OAuth 시작 API 응답입니다."""

    authorization_url: str
    expires_at: datetime


class OpenAiAuthStatusResponse(BaseModel):
    """OpenAI OAuth 상태 조회 API 응답입니다."""

    state: OpenAiAuthStatus
    connected: bool
    pending: bool
    account_email: str | None = None
    account_id: str | None = None
    expires_at: datetime | None = None
    scopes: list[str] = Field(default_factory=list)
