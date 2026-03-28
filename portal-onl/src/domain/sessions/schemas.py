from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from domain.datasets.schemas import (
    DatasetDetail,
    DatasetPreviewResponse,
    DatasetProfileResponse,
)
from domain.shared import AnalyticsPayload, WorkspacePayload


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


class SessionSnapshotResponse(BaseModel):
    session: SessionDetail
    messages: list[SessionMessage]
    dataset_ids: list[str]
    datasets: list[SessionSnapshotDataset]
    analytics: AnalyticsPayload | None = None
    workspace: WorkspacePayload | None = None
