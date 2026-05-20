import math
from typing import Any

from core.utils import read_string
from features.tools.duckdb_sql import (
    execute_dataset_sql,
    list_numeric_columns,
    load_source_path,
    quote_identifier,
)
from features.tools.dto import ToolExecutionResult


def tool_definition() -> dict[str, object]:
    """상관관계 분석용 에이전트 tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "correlation",
        "description": (
            "source_id로 지정한 원천 데이터 파일을 DuckDB로 직접 scan하여 숫자형 컬럼 간 "
            "상관계수 행렬을 계산합니다. 전체 파일을 pandas DataFrame으로 적재하지 않습니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source_id": {
                    "type": "string",
                    "description": "상관관계를 계산할 원천 데이터 파일 source_id입니다.",
                },
                "columns": {
                    "type": ["array", "null"],
                    "items": {"type": "string"},
                    "description": "상관관계 계산에 포함할 숫자형 컬럼 목록입니다. 전체 숫자형 컬럼을 쓰려면 null입니다.",
                },
            },
            "required": ["source_id", "columns"],
            "additionalProperties": False,
        },
    }


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 DuckDB 상관관계 행렬을 계산합니다."""
    source_id = read_string(arguments.get("source_id"))
    if source_id is None:
        return _error_result("source_id is required.")

    selected_columns = _read_columns(arguments.get("columns"))
    if isinstance(selected_columns, str):
        return _error_result(selected_columns)

    try:
        source_path = load_source_path(source_id)
        columns = _resolve_columns(source_path, selected_columns)
        matrix = compute_correlation_matrix(source_path, columns=columns)
    except KeyError:
        return _error_result("Source not found.")
    except ValueError as exc:
        return _error_result(str(exc))

    data = {
        "source_id": source_id,
        "columns": columns,
        "correlation_matrix": matrix,
    }
    return _success_result(data)


def compute_correlation_matrix(
    source_path,
    *,
    columns: list[str],
) -> dict[str, dict[str, float]]:
    """DuckDB aggregate corr 함수로 전체 DataFrame 적재 없이 상관계수 행렬을 계산합니다."""
    select_parts: list[str] = []
    aliases: dict[str, tuple[str, str]] = {}
    for left_index, left in enumerate(columns):
        for right_index, right in enumerate(columns):
            alias = f"corr_{left_index}_{right_index}"
            aliases[alias] = (left, right)
            select_parts.append(
                "corr("
                f"try_cast({quote_identifier(left)} AS DOUBLE), "
                f"try_cast({quote_identifier(right)} AS DOUBLE)"
                f") AS {quote_identifier(alias)}"
            )

    result = execute_dataset_sql(
        source_path,
        f"SELECT {', '.join(select_parts)} FROM dataset",
    )
    if result.empty:
        raise ValueError("Correlation query returned no rows.")

    row = result.iloc[0].to_dict()
    matrix = {column: {} for column in columns}
    for alias, (left, right) in aliases.items():
        matrix[left][right] = _to_json_float(row.get(alias))
    return matrix


def _resolve_columns(source_path, selected_columns: list[str] | None) -> list[str]:
    """요청 컬럼이 있으면 검증하고, 없으면 DuckDB numeric 컬럼을 사용합니다."""
    numeric_columns = list_numeric_columns(source_path)
    if selected_columns:
        missing = [column for column in selected_columns if column not in numeric_columns]
        if missing:
            raise ValueError(f"Unknown or non-numeric columns: {', '.join(missing)}")
        columns = selected_columns
    else:
        columns = numeric_columns

    if len(columns) < 2:
        raise ValueError("At least two numeric columns are required for correlation.")
    return columns


def _read_columns(value: object) -> list[str] | str | None:
    """선택 입력인 columns를 중복 없는 문자열 배열로 정규화합니다."""
    if value is None:
        return None
    if not isinstance(value, list):
        return "columns must be an array."

    columns: list[str] = []
    for item in value:
        column = read_string(item)
        if column is None:
            return "columns must contain only non-empty strings."
        if column not in columns:
            columns.append(column)
    return columns


def _to_json_float(value: object) -> float:
    """DuckDB numeric 결과를 JSON 안전 float으로 변환합니다."""
    if value is None:
        return 0.0
    number = float(value)
    return number if math.isfinite(number) else 0.0


def _success_result(data: dict[str, Any]) -> dict[str, object]:
    """상관관계 계산 성공 결과를 공통 DTO 형식으로 반환합니다."""
    return ToolExecutionResult[dict[str, Any]](ok=True, data=data).model_dump(
        mode="json",
        exclude_none=True,
    )


def _error_result(message: str) -> dict[str, object]:
    """상관관계 계산 실패 결과를 공통 DTO 형식으로 반환합니다."""
    return ToolExecutionResult[object](ok=False, error=message).model_dump(
        mode="json",
        exclude_none=True,
    )
