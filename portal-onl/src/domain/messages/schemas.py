from pydantic import BaseModel, Field

from agents.state import AgentRoute, PlanStep
from domain.datasets.schemas import (
    DatasetInfo,
    DatasetPreviewResponse,
    DatasetProfileResponse,
)
from domain.shared import AnalyticsPayload, ReasoningStatus, WorkspacePayload


class ChatRequest(BaseModel):
    session_id: str
    message: str
    dataset_ids: list[str] = Field(default_factory=list)


class MessageStreamRequest(BaseModel):
    session_id: str
    message: str = ""
    uploaded_dataset_ids: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    session_id: str
    assistant_message: str
    route: AgentRoute = "conversation"
    used_tools: list[str] = Field(default_factory=list)
    plan: list[PlanStep] = Field(default_factory=list)
    plan_explanation: str | None = None
    status: ReasoningStatus = "completed"
    analytics: AnalyticsPayload | None = None
    workspace: WorkspacePayload | None = None


class ChatInteractionDataset(BaseModel):
    detail: DatasetInfo
    preview: DatasetPreviewResponse
    profile: DatasetProfileResponse
