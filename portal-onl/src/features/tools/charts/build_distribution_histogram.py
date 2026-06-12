from features.tools.charts.common import tool_error, tool_success
from features.tools.charts.sql_common import build_sql_axis_chart, sql_chart_parameters


def tool_definition() -> dict[str, object]:
    """distribution histogram chart 생성 tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "build_distribution_histogram",
        "description": (
            "datafile_path를 DuckDB dataset view로 조회한 SQL 결과를 "
            "분포와 빈도용 histogram chart payload로 생성합니다."
        ),
        "parameters": sql_chart_parameters(),
    }


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 distribution histogram chart를 생성합니다."""
    try:
        datafile_path, chart = build_sql_axis_chart(
            arguments,
            chart_id="distribution_histogram",
            chart_type="histogram",
        )
    except ValueError as exc:
        return tool_error(str(exc))
    return tool_success(
        {"datafile_path": str(datafile_path), "chart": chart.model_dump(mode="json")}
    )
