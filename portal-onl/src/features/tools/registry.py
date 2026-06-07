import json
import logging
from typing import Protocol

from features.tools.analysis import dataframe_context
from features.tools.charts import (
    build_category_area,
    build_category_bar,
    build_correlation_scatter,
    build_distribution_histogram,
    build_segment_bubble_chart,
    build_share_donut,
    build_trend_chart,
)
from features.tools.datasets import (
    get_dataset_info,
    inspect_dataset_context,
)
from features.tools.planning import update_plan
from features.tools.workspace_files import (
    run_cli_command,
)
from features.tools.workspace_files.context import clear_workspace_file_context

logger = logging.getLogger(__name__)


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
    get_dataset_info,
    build_trend_chart,
    build_category_bar,
    build_category_area,
    build_correlation_scatter,
    build_segment_bubble_chart,
    build_distribution_histogram,
    build_share_donut,
    run_cli_command,
)
_TOOL_ALIASES: dict[str, ToolModule] = {
    "build_trend_chart": build_trend_chart,
    "build_category_bar": build_category_bar,
    "build_category_area": build_category_area,
    "build_correlation_scatter": build_correlation_scatter,
    "build_segment_bubble_chart": build_segment_bubble_chart,
    "build_distribution_histogram": build_distribution_histogram,
    "build_share_donut": build_share_donut,
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
        result = {"ok": False, "error": f"Unsupported tool: {name}"}
        _log_tool_failure(name=name, arguments=arguments, result=result)
        return result

    parsed_arguments = _parse_tool_arguments(arguments)
    if parsed_arguments is None:
        result = {"ok": False, "error": f"Invalid tool arguments for: {name}"}
        _log_tool_failure(name=name, arguments=arguments, result=result)
        return result

    logger.debug(
        "Executing tool name=%s argument_keys=%s",
        name,
        sorted(parsed_arguments.keys()),
    )
    try:
        result = tool.execute(parsed_arguments)
    except Exception:
        logger.exception(
            "Tool execution raised exception name=%s arguments_preview=%s",
            name,
            _preview_tool_arguments(parsed_arguments),
        )
        raise

    if result.get("ok") is False:
        _log_tool_failure(name=name, arguments=parsed_arguments, result=result)
    else:
        logger.debug("Tool execution completed name=%s ok=%s", name, result.get("ok"))
    return result


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


def _log_tool_failure(
    *,
    name: str,
    arguments: dict[str, object] | str | None,
    result: dict[str, object],
) -> None:
    """tool 실패 원인을 콘솔/파일 로그에서 바로 확인할 수 있게 남깁니다."""
    logger.warning(
        "Tool execution failed name=%s error=%s errors=%s arguments_preview=%s data_preview=%s",
        name,
        result.get("error"),
        result.get("errors") or [],
        _preview_tool_arguments(arguments),
        _preview_tool_data(result.get("data")),
    )


def _preview_tool_arguments(arguments: dict[str, object] | str | None) -> object:
    """민감하거나 큰 payload를 피하기 위해 tool argument를 짧게 요약합니다."""
    if arguments is None:
        return None
    if isinstance(arguments, str):
        return _truncate_log_value(arguments)
    return {
        key: _preview_tool_value(value)
        for key, value in arguments.items()
        if key not in {"content"}
    }


def _preview_tool_data(data: object) -> object:
    """실패 data payload가 큰 경우 로그 크기를 제한합니다."""
    return _preview_tool_value(data)


def _preview_tool_value(value: object) -> object:
    """로그 출력용으로 중첩 값을 작고 안전한 형태로 변환합니다."""
    if isinstance(value, str):
        return _truncate_log_value(value)
    if isinstance(value, list):
        return [_preview_tool_value(item) for item in value[:5]]
    if isinstance(value, dict):
        return {
            str(key): _preview_tool_value(child)
            for key, child in list(value.items())[:10]
            if key not in {"content"}
        }
    return value


def _truncate_log_value(value: str) -> str:
    """긴 문자열은 로그 가독성을 위해 앞부분만 유지합니다."""
    normalized = " ".join(value.split())
    if len(normalized) <= 500:
        return normalized
    return f"{normalized[:497]}..."
