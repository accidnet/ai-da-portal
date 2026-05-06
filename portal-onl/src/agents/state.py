from typing import Literal, TypedDict

from domain.shared import AnalyticsPayload, ReasoningStatus, WorkspacePayload

AgentRoute = Literal["conversation", "dataset_analysis", "analysis_request"]


class PlanStep(TypedDict):
    step: str
    status: Literal["pending", "in_progress", "completed"]


class AgentInvokeInput(TypedDict, total=False):
    """agent 실행에 필요한 외부 입력 값입니다."""

    session_id: str
    message: str
    dataset_ids: list[str]


class AgentInvokeOutput(TypedDict, total=False):
    """agent 실행이 완료된 뒤 저장/응답에 쓰는 출력 값입니다."""

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


class AgentState(AgentInvokeInput, AgentInvokeOutput, total=False):
    """이전 호출부 호환을 위한 입력/출력 통합 타입입니다."""


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
