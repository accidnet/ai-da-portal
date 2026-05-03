from dataclasses import dataclass
from typing import Protocol

from agents.state import AgentState
from tools import run_portal_analysis, update_plan
from tools.datasets import inspect_dataset_context, load_uploaded_dataset_file


class ToolExecutor(Protocol):
    def __call__(
        self, state: AgentState, arguments: dict[str, object]
    ) -> dict[str, object]: ...


@dataclass(slots=True)
class ToolRuntimeContext:
    dataset_service: object
    analysis_service: object
    resolve_dataset_id: object
    available_dataset_ids: object
    read_string: object
    read_bool: object
    require_string: object


def get_tool_definitions() -> list[dict[str, object]]:
    """에이전트에서 사용하는 툴 정의 목록을 중앙 관리합니다."""

    return [
        update_plan.tool_definition(),
        inspect_dataset_context.tool_definition(),
        run_portal_analysis.tool_definition(),
        load_uploaded_dataset_file.tool_definition(),
    ]


def execute_tool(
    name: str,
    state: AgentState,
    arguments: dict[str, object],
    context: ToolRuntimeContext,
) -> dict[str, object]:
    executors: dict[str, ToolExecutor] = {
        "update_plan": lambda tool_state, tool_arguments: update_plan.execute(
            tool_state, tool_arguments
        ),
        "inspect_dataset_context": lambda _tool_state, tool_arguments: inspect_dataset_context.execute(
            tool_arguments
        ),
        "run_portal_analysis": lambda tool_state, tool_arguments: run_portal_analysis.execute(
            tool_state,
            tool_arguments,
            dataset_service=context.dataset_service,
            analysis_service=context.analysis_service,
            resolve_dataset_id=context.resolve_dataset_id,
            available_dataset_ids=context.available_dataset_ids,
            read_string=context.read_string,
            require_string=context.require_string,
        ),
        "load_uploaded_dataset_file": lambda _tool_state, tool_arguments: load_uploaded_dataset_file.execute(
            tool_arguments,
            dataset_service=context.dataset_service,
            read_string=context.read_string,
        ),
    }
    executor = executors.get(name)
    if executor is None:
        return {"ok": False, "error": f"Unsupported tool: {name}"}
    return executor(state, arguments)
