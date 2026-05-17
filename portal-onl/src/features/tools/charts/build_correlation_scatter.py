import pandas as pd

from core.utils import read_string
from domain.shared import ChartMeta, ChartPayload, ChartPoint
from shared.integrations.ai.contracts import Function
from features.tools.charts.common import tool_error, tool_success

from features.tools.duckdb_sql import (
    execute_select_sql,
    load_dataset_path,
    read_limit,
    read_required_string,
)


def tool_definition() -> dict[str, object]:
    """correlation scatter chart 생성 tool 정의를 반환합니다."""
    definition = Function(
        name="build_correlation_scatter",
        description=(
            "DuckDB에서 실행할 읽기 전용 SQL을 기반으로 상관관계 산점도 렌더링에 필요한 "
            "데이터와 차트 메타데이터를 생성합니다. 두 숫자형 지표 간 관계, 분포, "
            "이상치를 비교하는 분석에 사용합니다."
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
                        "x축 숫자 컬럼과 y축 숫자 컬럼을 포함해야 합니다. "
                        "예: SELECT avg_order_value, repurchase_rate, customer_segment "
                        "FROM dataset WHERE avg_order_value IS NOT NULL "
                        "AND repurchase_rate IS NOT NULL LIMIT 500"
                    ),
                },
                "chart_type": {
                    "type": "string",
                    "enum": ["scatter"],
                    "description": "상관관계 분석용 차트 타입입니다. 산점도는 scatter만 사용합니다.",
                },
                "x_axis": {
                    "type": "string",
                    "description": "x축으로 사용할 숫자형 컬럼명입니다.",
                },
                "y_axis": {
                    "type": "string",
                    "description": "y축으로 사용할 숫자형 컬럼명입니다.",
                },
                "label_column": {
                    "type": ["string", "null"],
                    "description": "각 점의 tooltip label로 사용할 컬럼명입니다. 없으면 null입니다.",
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
                "label_column",
                "title",
                "description",
                "limit",
            ],
            "additionalProperties": False,
        },
    )
    return definition.model_dump(mode="json", exclude_none=True)


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 correlation scatter chart를 생성합니다."""
    try:
        dataset_id = read_required_string(arguments, "dataset_id")
        sql = read_required_string(arguments, "sql")
        x_axis = read_required_string(arguments, "x_axis")
        y_axis = read_required_string(arguments, "y_axis")
        title = read_required_string(arguments, "title")
        chart_type = read_string(arguments.get("chart_type")) or "scatter"
        label_column = read_string(arguments.get("label_column"))
        limit = read_limit(arguments.get("limit"))
        dataset_path = load_dataset_path(dataset_id)
        result = execute_select_sql(dataset_path, sql, limit)
        chart = _build_sql_correlation_scatter(
            result,
            x_axis=x_axis,
            y_axis=y_axis,
            label_column=label_column,
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


def _build_sql_correlation_scatter(
    dataframe: pd.DataFrame,
    *,
    x_axis: str,
    y_axis: str,
    label_column: str | None,
    title: str,
    chart_type: str,
) -> ChartPayload:
    """SQL 결과 컬럼을 기반으로 correlation scatter chart payload를 생성합니다."""
    if chart_type != "scatter":
        raise ValueError("chart_type must be scatter.")

    required_columns = [x_axis, y_axis]
    if label_column is not None:
        required_columns.append(label_column)
    missing_columns = [
        column for column in required_columns if column not in dataframe.columns
    ]
    if missing_columns:
        raise ValueError(f"SQL result is missing columns: {', '.join(missing_columns)}.")

    # 프론트 scatter 렌더러는 points[].x/y를 숫자로 받으므로 명시적으로 변환합니다.
    normalized = dataframe.copy()
    normalized[x_axis] = pd.to_numeric(normalized[x_axis], errors="coerce")
    normalized[y_axis] = pd.to_numeric(normalized[y_axis], errors="coerce")
    normalized = normalized.dropna(subset=[x_axis, y_axis])
    if normalized.empty:
        raise ValueError("x_axis and y_axis must contain numeric values.")

    points = [
        ChartPoint(
            x=float(row[x_axis]),
            y=float(row[y_axis]),
            label=_format_point_label(row[label_column])
            if label_column is not None
            else str(index),
        )
        for index, row in normalized.iterrows()
    ]
    return ChartPayload(
        id="correlation_scatter",
        type=chart_type,
        title=title,
        points=points,
        meta=ChartMeta(x_label=x_axis, y_label=y_axis),
    )


def _format_point_label(value: object) -> str | None:
    """tooltip label 값을 프론트 표시용 문자열로 변환합니다."""
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)
