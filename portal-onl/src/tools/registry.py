from typing import Protocol

from tools.analysis import anomaly_detection, correlation
from tools.charts import (
    build_category_bar,
    build_chart,
    build_chart_analytics,
    build_correlation_scatter,
    build_insight,
    build_share_donut,
    build_summary_cards,
    build_table,
    build_trend_chart,
    inspect_chart_columns,
    select_chart_spec,
)
from tools.datasets import inspect_dataset_context
from tools.planning import update_plan


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
    inspect_dataset_context,
    correlation,
    anomaly_detection,
    inspect_chart_columns,
    select_chart_spec,
    build_summary_cards,
    build_chart,
    build_correlation_scatter,
    build_trend_chart,
    build_share_donut,
    build_category_bar,
    build_table,
    build_insight,
    build_chart_analytics,
)


def get_tool_definitions() -> list[dict[str, object]]:
    """에이전트에서 사용하는 툴 정의 목록을 중앙 관리합니다."""

    return [tool.tool_definition() for tool in _TOOL_MODULES]


def execute_tool(name: str, arguments: dict[str, object]) -> dict[str, object]:
    """tool 이름 문자열과 arguments를 받아 정의된 tool의 execute 함수를 실행합니다."""
    tool = _find_tool(name)
    if tool is None:
        return {"ok": False, "error": f"Unsupported tool: {name}"}
    return tool.execute(arguments)


def _find_tool(name: str) -> ToolModule | None:
    """definition에 등록된 name과 일치하는 tool module을 찾습니다."""
    for tool in _TOOL_MODULES:
        if _tool_name(tool) == name:
            return tool
    return None


def _tool_name(tool: ToolModule) -> str | None:
    """tool definition에서 function name을 안전하게 읽습니다."""
    name = tool.tool_definition().get("name")
    return name if isinstance(name, str) else None
