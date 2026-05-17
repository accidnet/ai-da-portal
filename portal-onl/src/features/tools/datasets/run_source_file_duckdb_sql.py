from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import read_string
from features.data_sources.domain.models import DataSourceItem
from features.data_sources.infrastructure.repositories import DataSourceRepository
from shared.integrations.ai.contracts import Function
from features.tools.duckdb_sql import execute_select_sql, read_limit
from features.tools.dto import ToolExecutionError, ToolExecutionResult


def tool_definition() -> dict[str, object]:
    """원천 데이터 파일별 DuckDB SQL 실행 tool 정의를 반환합니다."""
    definition = Function(
        name="run_source_file_duckdb_sql",
        description=(
            "source_id로 지정한 원천 데이터 파일을 DuckDB dataset view로 열고 "
            "읽기 전용 SQL을 실행합니다. DuckDB SELECT/WITH 쿼리 안에서 필터링, "
            "정렬, 집계, 조인식, CTE, 윈도우 함수, 타입 변환, 날짜/문자열/수치 함수 등 "
            "DuckDB가 지원하는 분석 SQL 기능을 활용할 수 있습니다. 복수 source_id를 "
            "사용할 때는 queries 배열에 source_id와 sql을 1:1로 매핑합니다."
        ),
        parameters={
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "description": "source_id와 해당 파일에 실행할 DuckDB SELECT/WITH SQL 목록입니다.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source_id": {
                                "type": "string",
                                "description": "SQL을 실행할 원천 데이터 파일 ID입니다.",
                            },
                            "sql": {
                                "type": "string",
                                "description": (
                                    "DuckDB에서 실행할 읽기 전용 SELECT/WITH SQL입니다. "
                                    "대상 파일은 dataset view로 참조합니다. "
                                    "DuckDB의 집계, CTE, 윈도우 함수, CASE, CAST, 날짜/문자열/수치 함수 등을 사용할 수 있습니다. "
                                    "예: SELECT region, SUM(sales) AS sales "
                                    "FROM dataset GROUP BY region ORDER BY sales DESC"
                                ),
                            },
                        },
                        "required": ["source_id", "sql"],
                        "additionalProperties": False,
                    },
                    "minItems": 1,
                },
                "limit": {
                    "type": "integer",
                    "description": "각 SQL 결과에서 반환할 최대 행 수입니다.",
                    "minimum": 1,
                    "maximum": 5000,
                },
            },
            "required": ["queries", "limit"],
            "additionalProperties": False,
        },
    )
    return definition.model_dump(mode="json", exclude_none=True)


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 source별 SQL을 실행합니다."""
    try:
        query_specs = _read_query_specs(arguments.get("queries"))
        limit = read_limit(arguments.get("limit"))
    except ValueError as exc:
        return ToolExecutionResult[object](ok=False, error=str(exc)).model_dump(
            mode="json", exclude_none=True
        )

    source_items = _get_source_items([spec["source_id"] for spec in query_specs])
    results: list[dict[str, object]] = []
    errors: list[ToolExecutionError] = []

    for spec in query_specs:
        source_id = spec["source_id"]
        source_item = source_items.get(source_id)
        if source_item is None:
            errors.append(ToolExecutionError(target_id=source_id, message="Source not found."))
            continue

        try:
            results.append(_execute_query(source_item, spec["sql"], limit))
        except ValueError as exc:
            errors.append(ToolExecutionError(target_id=source_id, message=str(exc)))

    return ToolExecutionResult[dict[str, object]](
        ok=not errors,
        data={"queries": results},
        errors=errors,
    ).model_dump(mode="json", exclude_none=True)


def _read_query_specs(value: object) -> list[dict[str, str]]:
    """tool arguments에서 source_id/sql 매핑 목록을 정규화합니다."""
    if not isinstance(value, list) or not value:
        raise ValueError("queries must be a non-empty array.")

    query_specs: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("each query must be an object.")

        source_id = read_string(item.get("source_id"))
        sql = read_string(item.get("sql"))
        if source_id is None:
            raise ValueError("source_id is required for each query.")
        if sql is None:
            raise ValueError("sql is required for each query.")
        query_specs.append({"source_id": source_id, "sql": sql})
    return query_specs


def _get_source_items(source_ids: list[str]) -> dict[str, DataSourceItem]:
    """source_id 목록에 해당하는 원천 데이터 파일 노드를 조회합니다."""
    unique_source_ids = list(dict.fromkeys(source_ids))
    items = DataSourceRepository().list_items_by_ids(unique_source_ids)
    return {item.id: item for item in items}


def _execute_query(
    source_item: DataSourceItem,
    sql: str,
    limit: int,
) -> dict[str, object]:
    """단일 source 파일에 DuckDB SQL을 실행하고 JSON 응답 payload를 생성합니다."""
    if source_item.item_type != "file":
        raise ValueError("Source must be a file.")
    if source_item.storage_path is None:
        raise ValueError("Source storage path is missing.")

    dataframe = execute_select_sql(Path(source_item.storage_path), sql, limit)
    return {
        "source_id": source_item.id,
        "source_name": source_item.name,
        "relative_path": source_item.relative_path,
        "row_count": len(dataframe),
        "columns": [str(column) for column in dataframe.columns],
        "rows": _serialize_rows(dataframe),
    }


def _serialize_rows(dataframe: pd.DataFrame) -> list[dict[str, object]]:
    """DataFrame 결과를 JSON 직렬화 가능한 row 목록으로 변환합니다."""
    rows: list[dict[str, object]] = []
    for record in dataframe.to_dict(orient="records"):
        rows.append({str(key): _serialize_value(value) for key, value in record.items()})
    return rows


def _serialize_value(value: Any) -> object:
    """pandas/numpy scalar 값을 JSON 응답에서 안전한 값으로 변환합니다."""
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime | date):
        return value.isoformat()
    if hasattr(value, "item"):
        scalar = value.item()
        return scalar if isinstance(scalar, str | int | float | bool) else str(scalar)
    if isinstance(value, str | int | float | bool):
        return value
    return str(value)
