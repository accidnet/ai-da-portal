from datetime import date, datetime
import re
from typing import Any

import duckdb
import pandas as pd

from core.utils import read_string
from features.data_sources.domain.models import DataSourceItem
from features.data_sources.infrastructure.repositories import DataSourceRepository
from features.tools.duckdb_sql import (
    create_source_view,
    read_limit,
    resolve_source_file_path,
)
from features.tools.dto import ToolExecutionError, ToolExecutionResult
from shared.integrations.ai.contracts import Function


_ALIAS_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def tool_definition() -> dict[str, object]:
    """복수 원천 데이터 파일 DuckDB SQL 실행 tool 정의를 반환합니다."""
    definition = Function(
        name="run_combined_source_files_duckdb_sql",
        description=(
            "여러 source_id 원천 데이터 파일을 하나의 DuckDB connection에 동시에 view로 등록하고 "
            "단일 SELECT/WITH SQL을 실행합니다. 파일 간 JOIN, UNION, 통합 집계, 공통 키 기준 비교처럼 "
            "여러 파일을 함께 분석해야 할 때 사용합니다. sources의 alias를 SQL에서 테이블/view 이름으로 "
            "참조합니다. alias를 생략하면 s1, s2 순서로 생성됩니다."
        ),
        parameters={
            "type": "object",
            "properties": {
                "sources": {
                    "type": "array",
                    "description": (
                        "하나의 SQL에서 동시에 참조할 원천 데이터 파일 목록입니다. alias는 SQL view 이름입니다."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "source_id": {
                                "type": "string",
                                "description": "DuckDB view로 등록할 원천 데이터 파일 ID입니다.",
                            },
                            "alias": {
                                "type": ["string", "null"],
                                "description": (
                                    "SQL에서 사용할 view 이름입니다. 영문/숫자/_만 허용하며 숫자로 시작할 수 없습니다. "
                                    "예: customers, transactions. null이면 s1, s2 순서로 자동 생성합니다."
                                ),
                            },
                        },
                        "required": ["source_id", "alias"],
                        "additionalProperties": False,
                    },
                    "minItems": 1,
                    "maxItems": 20,
                },
                "sql": {
                    "type": "string",
                    "description": (
                        "sources alias view를 참조하는 읽기 전용 DuckDB SELECT/WITH SQL입니다. "
                        "예: SELECT c.customer_id, SUM(t.amount) AS amount "
                        "FROM customers c JOIN transactions t USING (customer_id) "
                        "GROUP BY c.customer_id ORDER BY amount DESC"
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "SQL 결과에서 반환할 최대 행 수입니다.",
                    "minimum": 1,
                    "maximum": 5000,
                },
            },
            "required": ["sources", "sql", "limit"],
            "additionalProperties": False,
        },
    )
    return definition.model_dump(mode="json", exclude_none=True)


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 복수 source DuckDB SQL을 실행합니다."""
    try:
        source_specs = _read_source_specs(arguments.get("sources"))
        sql = _read_sql(arguments.get("sql"))
        limit = read_limit(arguments.get("limit"))
    except ValueError as exc:
        return ToolExecutionResult[object](ok=False, error=str(exc)).model_dump(
            mode="json",
            exclude_none=True,
        )

    source_items = _get_source_items([spec["source_id"] for spec in source_specs])
    missing_errors = [
        ToolExecutionError(target_id=spec["source_id"], message="Source not found.")
        for spec in source_specs
        if source_items.get(spec["source_id"]) is None
    ]
    if missing_errors:
        return ToolExecutionResult[object](ok=False, errors=missing_errors).model_dump(
            mode="json",
            exclude_none=True,
        )

    try:
        data = _execute_join_query(source_specs, source_items, sql, limit)
    except ValueError as exc:
        return ToolExecutionResult[object](ok=False, error=str(exc)).model_dump(
            mode="json",
            exclude_none=True,
        )

    return ToolExecutionResult[dict[str, object]](ok=True, data=data).model_dump(
        mode="json",
        exclude_none=True,
    )


def _read_source_specs(value: object) -> list[dict[str, str]]:
    """tool arguments에서 source_id와 alias 목록을 정규화합니다."""
    if not isinstance(value, list) or not value:
        raise ValueError("sources must be a non-empty array.")

    source_specs: list[dict[str, str]] = []
    aliases: set[str] = set()
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError("each source must be an object.")

        source_id = read_string(item.get("source_id"))
        alias = read_string(item.get("alias")) or f"s{index}"
        if source_id is None:
            raise ValueError("source_id is required for each source.")
        if not _ALIAS_PATTERN.fullmatch(alias):
            raise ValueError(
                "source alias must start with a letter or _ and contain only letters, numbers, and _."
            )
        if alias in aliases:
            raise ValueError(f"duplicate source alias: {alias}")
        aliases.add(alias)
        source_specs.append({"source_id": source_id, "alias": alias})
    return source_specs


def _read_sql(value: object) -> str:
    """읽기 전용 SQL 문자열을 정규화합니다."""
    sql = read_string(value)
    if sql is None:
        raise ValueError("sql is required.")

    normalized_sql = sql.strip().rstrip(";").strip()
    if ";" in normalized_sql:
        raise ValueError("sql must contain a single SELECT statement.")
    if not normalized_sql.lower().startswith(("select ", "with ")):
        raise ValueError("sql must be a read-only SELECT/WITH query.")
    return normalized_sql


def _get_source_items(source_ids: list[str]) -> dict[str, DataSourceItem]:
    """source_id 목록에 해당하는 원천 데이터 파일 노드를 조회합니다."""
    unique_source_ids = list(dict.fromkeys(source_ids))
    items = DataSourceRepository().list_items_by_ids(unique_source_ids)
    return {item.id: item for item in items}


def _execute_join_query(
    source_specs: list[dict[str, str]],
    source_items: dict[str, DataSourceItem],
    sql: str,
    limit: int,
) -> dict[str, object]:
    """복수 source view를 생성하고 단일 SQL 결과를 JSON payload로 반환합니다."""
    connection = duckdb.connect(database=":memory:")
    try:
        sources = []
        for spec in source_specs:
            source_item = source_items[spec["source_id"]]
            source_path = resolve_source_file_path(source_item)
            create_source_view(connection, source_path, spec["alias"])
            sources.append(
                {
                    "source_id": source_item.id,
                    "alias": spec["alias"],
                    "source_name": source_item.name,
                    "relative_path": source_item.relative_path,
                }
            )

        limited_sql = f"SELECT * FROM ({sql}) AS duckdb_result LIMIT {limit}"
        dataframe = connection.execute(limited_sql).fetchdf()
    except duckdb.Error as exc:
        raise ValueError(f"Failed to execute SQL: {exc}") from exc
    finally:
        connection.close()

    if dataframe.empty:
        raise ValueError("SQL returned no rows.")

    return {
        "sources": sources,
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
