from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from domain.shared import AnalyticsPayload, ReasoningStatus, WorkspacePayload


class AnalysisRequest(BaseModel):
    session_id: str
    dataset_id: str | None = None
    analysis_type: Literal[
        "dataset_profile",
        "descriptive_summary",
        "correlation",
        "trend",
        "grouped_aggregation",
        "anomaly_detection",
    ]
    prompt: str | None = None


class AnalysisDetail(BaseModel):
    id: str
    session_id: str
    dataset_id: str | None = None
    analysis_type: str
    status: ReasoningStatus = "queued"
    created_at: datetime
    analytics: AnalyticsPayload | None = None
    workspace: WorkspacePayload | None = None


class AnalysisArtifactsResponse(BaseModel):
    analysis_id: str
    analytics: AnalyticsPayload
    workspace: WorkspacePayload | None = None
    notes: list[str] = Field(default_factory=list)
