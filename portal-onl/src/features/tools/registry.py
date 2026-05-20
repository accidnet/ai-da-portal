import json
from typing import Protocol

from features.tools.analysis import dataframe_context
from features.tools.analysis import anomaly_detection, correlation
from features.tools.charts import (
    build_correlation_scatter,
    build_trend_chart,
)
from features.tools.datasets import (
    inspect_dataset_context,
    run_source_file_duckdb_sql,
    run_source_files_duckdb_sql,
)
from features.tools.planning import update_plan
from features.tools.workspace_files import delete_path, list_files, read_file, write_file
from features.tools.workspace_files.context import clear_workspace_file_context


class ToolModule(Protocol):
    """registry에 등록 가능한 tool module 인터페이스입니다."""

    def tool_definition(self) -> dict[str, object]:
        """LLM에 노출할 tool definition을 반환합니다."""
        ...

    def execute(self, arguments: dict[str, object]) -> dict[str, object]:
        """LLM function_call arguments만 받아 tool을 실행합니다."""
        ...


_TOOL_MODULES: tuple[ToolModule, ...] = (
    update_plan,
    # inspect_dataset_context,
    run_source_file_duckdb_sql,
    run_source_files_duckdb_sql,
    correlation,
    anomaly_detection,
    build_trend_chart,
    build_correlation_scatter,
    list_files,
    read_file,
    write_file,
    delete_path,
)
_TOOL_ALIASES: dict[str, ToolModule] = {
    "run_source_file_duckdb_sql": run_source_file_duckdb_sql,
    "run_source_files_duckdb_sql": run_source_files_duckdb_sql,
    "build_trend_chart": build_trend_chart,
    "build_correlation_scatter": build_correlation_scatter,
}


def get_tool_definitions() -> list[dict[str, object]]:
    """에이전트에서 사용하는 툴 정의 목록을 중앙 관리합니다."""

    return [tool.tool_definition() for tool in _TOOL_MODULES]


def execute_tool(
    name: str, arguments: dict[str, object] | str | None
) -> dict[str, object]:
    """tool 이름 문자열과 arguments를 받아 정의된 tool의 execute 함수를 실행합니다."""
    tool = _find_tool(name)
    if tool is None:
        return {"ok": False, "error": f"Unsupported tool: {name}"}

    parsed_arguments = _parse_tool_arguments(arguments)
    if parsed_arguments is None:
        return {"ok": False, "error": f"Invalid tool arguments for: {name}"}

    return tool.execute(parsed_arguments)


def cleanup_runtime_memory() -> None:
    """agent 실행 후 tool 모듈의 요청 단위 캐시를 정리합니다."""
    dataframe_context.clear_runtime_memory()
    inspect_dataset_context.clear_runtime_memory()
    clear_workspace_file_context()


def _parse_tool_arguments(
    arguments: dict[str, object] | str | None,
) -> dict[str, object] | None:
    """Responses function_call arguments를 tool execute 입력 dict로 정규화합니다."""
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return arguments
    if not arguments.strip():
        return {}

    try:
        loaded = json.loads(arguments)
    except json.JSONDecodeError:
        return None

    return loaded if isinstance(loaded, dict) else None


def _find_tool(name: str) -> ToolModule | None:
    """definition에 등록된 name과 일치하는 tool module을 찾습니다."""
    alias_tool = _TOOL_ALIASES.get(name)
    if alias_tool is not None:
        return alias_tool

    for tool in _TOOL_MODULES:
        if _tool_name(tool) == name:
            return tool
    return None


def _tool_name(tool: ToolModule) -> str | None:
    """tool definition에서 function name을 안전하게 읽습니다."""
    name = tool.tool_definition().get("name")
    return name if isinstance(name, str) else None
