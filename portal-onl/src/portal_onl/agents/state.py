from typing import Literal, TypedDict

AgentRoute = Literal["conversation", "dataset_analysis", "analysis_request"]


class AgentState(TypedDict, total=False):
    session_id: str
    message: str
    dataset_ids: list[str]
    route: AgentRoute
    plan: list[str]
