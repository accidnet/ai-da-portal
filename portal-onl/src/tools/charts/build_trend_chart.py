import pandas as pd

from core.utils import read_string
from domain.shared import ChartMeta, ChartPayload, ChartSeries
from shared.integrations.ai.contracts import Function
from tools.charts.common import tool_error, tool_success

from .sql_query import (
    execute_select_sql,
    load_dataset_path,
    read_limit,
    read_required_string,
)


def tool_definition() -> dict[str, object]:
    """trend chart 생성 tool 정의를 반환합니다."""
    definition = Function(
        name="build_trend_chart",
        description=(
            "DuckDB에서 실행할 읽기 전용 SQL을 기반으로 추세 차트 렌더링에 필요한 "
            "데이터와 차트 메타데이터를 생성합니다. 시간 흐름에 따른 값의 증가/감소, "
            "월별/일별/분기별 추세 분석에 사용합니다."
        ),
        parameters={
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "string",
                    "description": "대상 데이터셋 ID입니다.",
                },
                "sql": {
                    "type": "string",
                    "description": (
                        "DuckDB에서 실행할 SELECT 전용 SQL입니다. "
                        "반드시 시각화에 필요한 컬럼만 조회하고, "
                        "시간 축 컬럼과 값 컬럼을 포함해야 합니다. "
                        "예: SELECT date_trunc('month', order_date) AS period, "
                        "SUM(sales) AS value FROM dataset "
                        "WHERE region = 'Seoul' GROUP BY 1 ORDER BY 1 LIMIT 500"
                    ),
                },
                "chart_type": {
                    "type": "string",
                    "enum": ["line"],
                    "description": "추세 분석용 차트 타입입니다. 추세 차트는 line만 사용합니다.",
                },
                "x_axis": {
                    "type": "string",
                    "description": "x축으로 사용할 컬럼명입니다. 보통 날짜/시간 컬럼입니다.",
                },
                "y_axis": {
                    "type": "string",
                    "description": "y축으로 사용할 컬럼명입니다. 보통 집계된 수치 컬럼입니다.",
                },
                "title": {
                    "type": "string",
                    "description": "차트 제목입니다.",
                },
                "description": {
                    "type": "string",
                    "description": "차트에 대한 간단한 설명입니다.",
                },
                "limit": {
                    "type": "integer",
                    "description": "반환할 최대 행 수입니다.",
                    "minimum": 1,
                    "maximum": 5000,
                },
            },
            "required": [
                "dataset_id",
                "sql",
                "chart_type",
                "x_axis",
                "y_axis",
                "title",
                "description",
                "limit",
            ],
            "additionalProperties": False,
        },
    )
    return definition.model_dump(mode="json", exclude_none=True)


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 trend chart를 생성합니다."""
    try:
        dataset_id = read_required_string(arguments, "dataset_id")
        sql = read_required_string(arguments, "sql")
        x_axis = read_required_string(arguments, "x_axis")
        y_axis = read_required_string(arguments, "y_axis")
        title = read_required_string(arguments, "title")
        chart_type = read_string(arguments.get("chart_type")) or "line"
        limit = read_limit(arguments.get("limit"))
        dataset_path = load_dataset_path(dataset_id)
        result = execute_select_sql(dataset_path, sql, limit)
        chart = _build_sql_trend_chart(
            result,
            x_axis=x_axis,
            y_axis=y_axis,
            title=title,
            chart_type=chart_type,
        )
    except KeyError:
        return tool_error("Dataset not found.")
    except ValueError as exc:
        return tool_error(str(exc))
    return tool_success(
        {"dataset_id": dataset_id, "chart": chart.model_dump(mode="json")}
    )


def _build_sql_trend_chart(
    dataframe: pd.DataFrame,
    *,
    x_axis: str,
    y_axis: str,
    title: str,
    chart_type: str,
) -> ChartPayload:
    """SQL 결과 컬럼을 기반으로 trend chart payload를 생성합니다."""
    if chart_type != "line":
        raise ValueError("chart_type must be line.")
    missing_columns = [
        column for column in (x_axis, y_axis) if column not in dataframe.columns
    ]
    if missing_columns:
        raise ValueError(f"SQL result is missing columns: {', '.join(missing_columns)}.")

    y_values = pd.to_numeric(dataframe[y_axis], errors="coerce")
    if y_values.notna().sum() == 0:
        raise ValueError("y_axis must contain numeric values.")

    x_labels = [_format_axis_label(value) for value in dataframe[x_axis]]
    return ChartPayload(
        id="trend_line",
        type=chart_type,
        title=title,
        x=x_labels,
        series=[
            ChartSeries(
                name=y_axis,
                data=[
                    float(value) if pd.notna(value) else None
                    for value in y_values
                ],
            )
        ],
        meta=ChartMeta(x_label=x_axis, y_label=y_axis),
    )


def _format_axis_label(value: object) -> str:
    """x축 값이 날짜형이면 ISO 문자열로, 그 외에는 문자열로 변환합니다."""
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)
