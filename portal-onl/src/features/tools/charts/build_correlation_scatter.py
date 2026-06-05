import pandas as pd

from core.utils import read_string
from features.tools.charts.dto import ChartMeta, ChartPayload, ChartPoint
from shared.integrations.ai.contracts import Function
from features.tools.charts.common import tool_error, tool_success

from features.tools.duckdb_sql import (
    execute_select_sql,
    load_source_path,
    read_limit,
    read_required_string,
)


def tool_definition() -> dict[str, object]:
    """correlation scatter chart 생성 tool 정의를 반환합니다."""
    definition = Function(
        name="build_correlation_scatter",
        description=(
            "두 숫자형 지표 간 관계, 분포, 이상치를 비교하는 scatter chart payload를 "
            "생성합니다. 각 점의 x/y 좌표와 tooltip label을 직접 전달합니다."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "차트 제목입니다.",
                },
                "x_label": {
                    "type": "string",
                    "description": "x축 제목입니다. 비교할 첫 번째 숫자형 지표명입니다.",
                },
                "y_label": {
                    "type": "string",
                    "description": "y축 제목입니다. 비교할 두 번째 숫자형 지표명입니다.",
                },
                "points": {
                    "type": "array",
                    "description": "산점도에 표시할 좌표 목록입니다.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "number",
                                "description": "x축에 표시할 숫자 값입니다.",
                            },
                            "y": {
                                "type": "number",
                                "description": "y축에 표시할 숫자 값입니다.",
                            },
                            "label": {
                                "type": ["string", "null"],
                                "description": "tooltip에 표시할 점 이름입니다. 없으면 null입니다.",
                            },
                        },
                        "required": ["x", "y", "label"],
                        "additionalProperties": False,
                    },
                    "minItems": 1,
                    "maxItems": 500,
                },
            },
            "required": ["title", "x_label", "y_label", "points"],
            "additionalProperties": False,
        },
    )
    return definition.model_dump(mode="json", exclude_none=True)


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 correlation scatter chart를 생성합니다."""
    if "points" in arguments:
        return _execute_direct(arguments)
    return _execute_sql(arguments)


def _execute_direct(arguments: dict[str, object]) -> dict[str, object]:
    """직접 전달된 point 값으로 correlation scatter chart를 생성합니다."""
    try:
        title = read_required_string(arguments, "title")
        x_label = read_required_string(arguments, "x_label")
        y_label = read_required_string(arguments, "y_label")
        points = _read_points(arguments.get("points"))
    except ValueError as exc:
        return tool_error(str(exc))

    chart = ChartPayload(
        id="correlation_scatter",
        type="scatter",
        title=title,
        points=points,
        meta=ChartMeta(x_label=x_label, y_label=y_label),
    )
    return tool_success({"chart": chart.model_dump(mode="json")})


def _execute_sql(arguments: dict[str, object]) -> dict[str, object]:
    """기존 SQL 기반 호출과의 호환성을 유지해 scatter chart를 생성합니다."""
    try:
        source_id = read_required_string(arguments, "source_id")
        sql = read_required_string(arguments, "sql")
        x_axis = read_required_string(arguments, "x_axis")
        y_axis = read_required_string(arguments, "y_axis")
        title = read_required_string(arguments, "title")
        chart_type = read_string(arguments.get("chart_type")) or "scatter"
        label_column = read_string(arguments.get("label_column"))
        limit = read_limit(arguments.get("limit"))
        source_path = load_source_path(source_id)
        result = execute_select_sql(source_path, sql, limit)
        chart = _build_sql_correlation_scatter(
            result,
            x_axis=x_axis,
            y_axis=y_axis,
            label_column=label_column,
            title=title,
            chart_type=chart_type,
        )
    except KeyError:
        return tool_error("Source not found.")
    except ValueError as exc:
        return tool_error(str(exc))
    return tool_success(
        {"source_id": source_id, "chart": chart.model_dump(mode="json")}
    )


def _read_points(value: object) -> list[ChartPoint]:
    """scatter point 목록을 ChartPoint로 정규화합니다."""
    if not isinstance(value, list) or not value:
        raise ValueError("points must be a non-empty array.")

    points: list[ChartPoint] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("each point must be an object.")
        points.append(
            ChartPoint(
                x=_read_number(item.get("x"), "x"),
                y=_read_number(item.get("y"), "y"),
                label=read_string(item.get("label")),
            )
        )
    return points


def _read_number(value: object, key: str) -> float:
    """좌표 값은 프론트 value axis에서 사용할 수 있는 숫자만 허용합니다."""
    if not isinstance(value, int | float):
        raise ValueError(f"{key} must be a number.")
    return float(value)


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
