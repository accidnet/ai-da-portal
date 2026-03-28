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


class SessionUpdateRequest(BaseModel):
    title: str | None = None
    preferred_dataset_id: str | None = None


class SessionLastDataset(BaseModel):
    id: str
    filename: str


class SessionSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    preferred_dataset_id: str | None = None
    message_count: int
    dataset_count: int
    last_dataset: SessionLastDataset | None = None


class SessionDetail(SessionSummary):
    pass


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


class SessionDatasetLinkRequest(BaseModel):
    dataset_id: str


class SessionDatasetLinkResponse(BaseModel):
    session_id: str
    dataset_ids: list[str]


class SessionDeleteResponse(BaseModel):
    id: str
    deleted: bool
