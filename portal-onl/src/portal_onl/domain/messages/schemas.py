from pydantic import BaseModel, Field

from portal_onl.domain.shared import AnalyticsPayload, ReasoningStatus


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
