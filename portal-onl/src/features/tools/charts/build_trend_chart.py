import pandas as pd

from core.utils import read_string
from features.tools.charts.dto import ChartMeta, ChartPayload, ChartSeries
from shared.integrations.ai.contracts import Function
from features.tools.charts.common import tool_error, tool_success

from features.tools.duckdb_sql import (
    execute_select_sql,
    load_source_path,
    read_limit,
    read_required_string,
)


def tool_definition() -> dict[str, object]:
    """trend chart 생성 tool 정의를 반환합니다."""
    definition = Function(
        name="build_trend_chart",
        description=(
            "시간 흐름에 따른 값의 증가/감소, 월별/일별/분기별 추세 분석에 사용하는 "
            "line chart payload를 생성합니다. x축 라벨과 series 값을 직접 전달합니다."
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
                    "description": "x축 제목입니다. 보통 날짜/기간/순서 기준입니다.",
                },
                "y_label": {
                    "type": "string",
                    "description": "y축 제목입니다. 보통 집계된 수치 지표명입니다.",
                },
                "x": {
                    "type": "array",
                    "description": "x축에 표시할 라벨 목록입니다.",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 500,
                },
                "series": {
                    "type": "array",
                    "description": "라인으로 표시할 series 목록입니다.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "series 이름입니다.",
                            },
                            "data": {
                                "type": "array",
                                "description": "x 라벨과 같은 순서의 숫자 값 목록입니다.",
                                "items": {"type": ["number", "null"]},
                                "minItems": 1,
                                "maxItems": 500,
                            },
                        },
                        "required": ["name", "data"],
                        "additionalProperties": False,
                    },
                    "minItems": 1,
                    "maxItems": 8,
                },
            },
            "required": ["title", "x_label", "y_label", "x", "series"],
            "additionalProperties": False,
        },
    )
    return definition.model_dump(mode="json", exclude_none=True)


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 trend chart를 생성합니다."""
    if "x" in arguments or "series" in arguments:
        return _execute_direct(arguments)
    return _execute_sql(arguments)


def _execute_direct(arguments: dict[str, object]) -> dict[str, object]:
    """직접 전달된 x/series 값으로 trend chart를 생성합니다."""
    try:
        title = read_required_string(arguments, "title")
        x_label = read_required_string(arguments, "x_label")
        y_label = read_required_string(arguments, "y_label")
        x_values = _read_x_labels(arguments.get("x"))
        series = _read_series(arguments.get("series"), expected_length=len(x_values))
    except ValueError as exc:
        return tool_error(str(exc))

    chart = ChartPayload(
        id="trend_line",
        type="line",
        title=title,
        x=x_values,
        series=series,
        meta=ChartMeta(x_label=x_label, y_label=y_label),
    )
    return tool_success({"chart": chart.model_dump(mode="json")})


def _execute_sql(arguments: dict[str, object]) -> dict[str, object]:
    """기존 SQL 기반 호출과의 호환성을 유지해 trend chart를 생성합니다."""
    try:
        source_id = read_required_string(arguments, "source_id")
        sql = read_required_string(arguments, "sql")
        x_axis = read_required_string(arguments, "x_axis")
        y_axis = read_required_string(arguments, "y_axis")
        title = read_required_string(arguments, "title")
        chart_type = read_string(arguments.get("chart_type")) or "line"
        limit = read_limit(arguments.get("limit"))
        source_path = load_source_path(source_id)
        result = execute_select_sql(source_path, sql, limit)
        chart = _build_sql_trend_chart(
            result,
            x_axis=x_axis,
            y_axis=y_axis,
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


def _read_x_labels(value: object) -> list[str]:
    """x축 라벨 목록을 프론트 표시 가능한 문자열로 정규화합니다."""
    if not isinstance(value, list) or not value:
        raise ValueError("x must be a non-empty array.")
    labels: list[str] = []
    for item in value:
        label = read_string(item)
        if label is None:
            raise ValueError("each x label must be a non-empty string.")
        labels.append(label)
    return labels


def _read_series(value: object, *, expected_length: int) -> list[ChartSeries]:
    """series 값을 차트 축 길이에 맞춰 검증하고 정규화합니다."""
    if not isinstance(value, list) or not value:
        raise ValueError("series must be a non-empty array.")

    series_list: list[ChartSeries] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("each series must be an object.")
        name = read_string(item.get("name"))
        if name is None:
            raise ValueError("each series needs a name.")
        data = _read_series_data(item.get("data"), expected_length=expected_length)
        series_list.append(ChartSeries(name=name, data=data))
    return series_list


def _read_series_data(value: object, *, expected_length: int) -> list[float | None]:
    """라인 렌더러가 안정적으로 처리할 수 있도록 숫자/null만 허용합니다."""
    if not isinstance(value, list) or not value:
        raise ValueError("series data must be a non-empty array.")
    if len(value) != expected_length:
        raise ValueError("each series data length must match x length.")

    data: list[float | None] = []
    for item in value:
        if item is None:
            data.append(None)
            continue
        if not isinstance(item, int | float):
            raise ValueError("series data values must be numbers or null.")
        data.append(float(item))
    return data


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
