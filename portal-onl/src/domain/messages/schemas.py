from typing import Annotated

from fastapi import Form
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

    @classmethod
    def as_form(
        cls,
        session_id: Annotated[str, Form(...)],
        message: Annotated[str, Form()] = "",
        uploaded_dataset_ids: Annotated[list[str] | None, Form()] = None,
    ) -> "MessageStreamRequest":
        # multipart form 필드를 스트리밍 요청 DTO로 바인딩합니다.
        return cls(
            session_id=session_id,
            message=message,
            uploaded_dataset_ids=list(uploaded_dataset_ids or []),
        )

    def to_chat_request(self, dataset_ids: list[str]) -> ChatRequest:
        # 스트리밍 요청을 에이전트 입력용 채팅 요청으로 변환합니다.
        return ChatRequest(
            session_id=self.session_id,
            message=self.message,
            dataset_ids=dataset_ids,
        )


class ChatResponse(BaseModel):
    session_id: str
    session_title: str
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
