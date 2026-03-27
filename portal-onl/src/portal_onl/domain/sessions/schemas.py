from datetime import datetime

from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    title: str = "New analysis session"


class SessionSummary(BaseModel):
    id: str
    title: str
    updated_at: datetime


class SessionDetail(SessionSummary):
    created_at: datetime
