from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from domain.datasets.schemas import (
    DatasetInfo,
    DatasetPreviewResponse,
    DatasetProfileResponse,
)
from domain.shared import AnalyticsPayload, WorkspacePayload

SessionMessageRoute = Literal["conversation", "dataset_analysis", "analysis_request"]


class SessionCreateRequest(BaseModel):
    title: str = "New analysis session"


class SessionUpdateRequest(BaseModel):
    title: str | None = None
    preferred_dataset_id: str | None = None


class SessionTitleRequest(BaseModel):
    user_message: str


class SessionTitleResponse(BaseModel):
    session_id: str
    title: str


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


class SessionSubMessage(BaseModel):
    id: str
    type: str
    text: str
    is_streaming: bool = False


class SessionPlanStep(BaseModel):
    step: str
    status: Literal["pending", "in_progress", "completed"]


class SessionMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    text: str
    created_at: datetime
    dataset_ids: list[str] = Field(default_factory=list)
    route: SessionMessageRoute | None = None
    used_tools: list[str] = Field(default_factory=list)
    plan: list[SessionPlanStep] = Field(default_factory=list)
    plan_explanation: str | None = None
    sub_messages: list[SessionSubMessage] = Field(default_factory=list)


class SessionSnapshotDataset(BaseModel):
    detail: DatasetInfo
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
