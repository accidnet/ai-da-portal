from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from domain.datasets.schemas import (
    DatasetDetail,
    DatasetPreviewResponse,
    DatasetProfileResponse,
)
from domain.shared import AnalyticsPayload


class SessionCreateRequest(BaseModel):
    title: str = "New analysis session"


class SessionSummary(BaseModel):
    id: str
    title: str
    updated_at: datetime


class SessionDetail(SessionSummary):
    created_at: datetime


class SessionMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    text: str
    created_at: datetime


class SessionSnapshotDataset(BaseModel):
    detail: DatasetDetail
    preview: DatasetPreviewResponse
    profile: DatasetProfileResponse


class SessionWorkspace(BaseModel):
    session_id: str
    dataset_ids: list[str]
    primary_dataset_id: str | None = None
    analysis_id: str | None = None
    analysis_type: str | None = None
    updated_at: datetime


class SessionSnapshotResponse(BaseModel):
    session: SessionDetail
    messages: list[SessionMessage]
    dataset_ids: list[str]
    datasets: list[SessionSnapshotDataset]
    analytics: AnalyticsPayload | None = None
    workspace: SessionWorkspace | None = None
