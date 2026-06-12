from features.tools.charts.common import tool_error, tool_success
from features.tools.charts.sql_common import build_sql_axis_chart, sql_chart_parameters


def tool_definition() -> dict[str, object]:
    """share donut chart 생성 tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "build_share_donut",
        "description": (
            "datafile_path를 DuckDB dataset view로 조회한 SQL 결과를 "
            "범주별 비중을 보여주는 donut chart payload로 생성합니다."
        ),
        "parameters": sql_chart_parameters(),
    }


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 share donut chart를 생성합니다."""
    try:
        datafile_path, chart = build_sql_axis_chart(
            arguments,
            chart_id="share_donut",
            chart_type="donut",
        )
    except ValueError as exc:
        return tool_error(str(exc))
    return tool_success(
        {"datafile_path": str(datafile_path), "chart": chart.model_dump(mode="json")}
    )
