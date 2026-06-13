from pathlib import Path

import pandas as pd

from core.utils import read_string
from features.tools.charts.dto import ChartId, ChartMeta, ChartPayload, ChartSeries, ChartType
from features.tools.duckdb_sql import (
    execute_select_sql,
    read_datafile_path,
    read_limit,
    read_required_string,
)


def sql_chart_parameters() -> dict[str, object]:
    """DuckDB SQL 기반 chart tool들이 공유하는 입력 schema를 반환합니다."""
    return {
        "type": "object",
        "properties": {
            "datafile_path": {
                "type": "string",
                "description": (
                    "DuckDB로 직접 읽을 CSV/TSV/JSON/Parquet 파일의 워크스페이스 루트 기준 상대 경로입니다. "
                    "workspace datasets 항목의 workspace_path 값을 사용하고 절대 경로는 사용하지 않습니다."
                ),
            },
            "sql": {
                "type": "string",
                "description": "datafile_path를 dataset view로 보고 실행할 SELECT/WITH SQL입니다.",
            },
            "title": {
                "type": "string",
                "description": "차트 제목입니다.",
            },
            "x_axis": {
                "type": "string",
                "description": "SQL 결과에서 x축 라벨로 사용할 컬럼명입니다.",
            },
            "y_axis": {
                "type": "string",
                "description": "SQL 결과에서 숫자 값으로 사용할 컬럼명입니다.",
            },
            "x_label": {
                "type": ["string", "null"],
                "description": "차트에 표시할 x축 제목입니다. 가능하면 사용자가 이해하기 쉬운 한국어 제목을 전달합니다. 없으면 x_axis 컬럼명을 사용합니다.",
            },
            "y_label": {
                "type": ["string", "null"],
                "description": "차트에 표시할 y축 제목입니다. 가능하면 단위나 집계 기준을 포함한 한국어 제목을 전달합니다. 없으면 y_axis 컬럼명을 사용합니다.",
            },
            "series_name": {
                "type": ["string", "null"],
                "description": "series 이름입니다. 없으면 y_axis를 사용합니다.",
            },
            "limit": {
                "type": ["integer", "null"],
                "description": "SQL 결과 최대 행 수입니다. 기본값은 500, 최대 5000입니다.",
            },
        },
        "required": ["datafile_path", "sql", "title", "x_axis", "y_axis"],
        "additionalProperties": False,
    }


def build_sql_axis_chart(
    arguments: dict[str, object],
    *,
    chart_id: ChartId,
    chart_type: ChartType,
) -> tuple[Path, ChartPayload]:
    """datafile_path와 SQL 결과를 프론트 축 기반 ChartPayload로 변환합니다."""
    datafile_path = read_datafile_path(arguments)
    sql = read_required_string(arguments, "sql")
    title = read_required_string(arguments, "title")
    x_axis = read_required_string(arguments, "x_axis")
    y_axis = read_required_string(arguments, "y_axis")
    x_label = read_string(arguments.get("x_label")) or x_axis
    y_label = read_string(arguments.get("y_label")) or y_axis
    series_name = read_string(arguments.get("series_name")) or y_axis
    limit = read_limit(arguments.get("limit"))

    dataframe = execute_select_sql(datafile_path, sql, limit)
    chart = _build_axis_chart_from_dataframe(
        dataframe,
        chart_id=chart_id,
        chart_type=chart_type,
        title=title,
        x_axis=x_axis,
        y_axis=y_axis,
        x_label=x_label,
        y_label=y_label,
        series_name=series_name,
    )
    return datafile_path, chart


def _build_axis_chart_from_dataframe(
    dataframe: pd.DataFrame,
    *,
    chart_id: ChartId,
    chart_type: ChartType,
    title: str,
    x_axis: str,
    y_axis: str,
    x_label: str,
    y_label: str,
    series_name: str,
) -> ChartPayload:
    """SQL 결과 컬럼을 프론트 차트 축/series 형식으로 정규화합니다."""
    missing_columns = [
        column for column in (x_axis, y_axis) if column not in dataframe.columns
    ]
    if missing_columns:
        raise ValueError(f"SQL result is missing columns: {', '.join(missing_columns)}.")

    y_values = pd.to_numeric(dataframe[y_axis], errors="coerce")
    if y_values.notna().sum() == 0:
        raise ValueError("y_axis must contain numeric values.")

    return ChartPayload(
        id=chart_id,
        type=chart_type,
        title=title,
        x=[format_axis_label(value) for value in dataframe[x_axis]],
        series=[
            ChartSeries(
                name=series_name,
                data=[
                    round(float(value), 4) if pd.notna(value) else None
                    for value in y_values
                ],
            )
        ],
        meta=ChartMeta(x_label=x_label, y_label=y_label),
    )


def format_axis_label(value: object) -> str:
    """x축 값이 날짜형이면 ISO 문자열로, 그 외에는 문자열로 변환합니다."""
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)
