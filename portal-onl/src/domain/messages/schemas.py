from pydantic import BaseModel, Field

from domain.datasets.schemas import (
    DatasetDetail,
    DatasetPreviewResponse,
    DatasetProfileResponse,
)
from domain.shared import AnalyticsPayload, ReasoningStatus, WorkspacePayload


class ChatRequest(BaseModel):
    session_id: str
    message: str
    dataset_ids: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    session_id: str
    assistant_message: str
    follow_up_suggestions: list[str] = Field(default_factory=list)
    status: ReasoningStatus = "completed"
    analytics: AnalyticsPayload | None = None
    workspace: WorkspacePayload | None = None


class ChatInteractionDataset(BaseModel):
    detail: DatasetDetail
    preview: DatasetPreviewResponse
    profile: DatasetProfileResponse


class ChatInteractionResponse(ChatResponse):
    dataset: ChatInteractionDataset | None = None
