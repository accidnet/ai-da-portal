from typing import Literal, TypedDict

from domain.shared import AnalyticsPayload, ReasoningStatus, WorkspacePayload

AgentRoute = Literal["conversation", "dataset_analysis", "analysis_request"]


class PlanStep(TypedDict):
    step: str
    status: Literal["pending", "in_progress", "completed"]


class AgentState(TypedDict, total=False):
    session_id: str
    message: str
    dataset_ids: list[str]
    session_dataset_ids: list[str]
    route: AgentRoute
    plan: list[PlanStep]
    plan_explanation: str | None
    assistant_message: str
    analytics: AnalyticsPayload | None
    workspace: WorkspacePayload | None
    resolved_dataset_id: str | None
    analysis_type: str | None
    response_id: str | None
    used_tools: list[str]
    status: ReasoningStatus


class AgentStateSnapshot(TypedDict):
    route: AgentRoute
    assistant_message: str
    used_tools: list[str]
    plan: list[PlanStep]
    plan_explanation: str | None
    analytics: AnalyticsPayload | None
    workspace: WorkspacePayload | None
    resolved_dataset_id: str | None
    analysis_type: str | None
    status: ReasoningStatus
