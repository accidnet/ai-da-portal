import math
from typing import Any

from core.utils import read_string
from features.tools.duckdb_sql import (
    execute_dataset_sql,
    list_numeric_columns,
    load_source_path,
    quote_identifier,
    read_limit,
)
from features.tools.dto import ToolExecutionResult


def tool_definition() -> dict[str, object]:
    """이상치 탐지용 에이전트 tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "anomaly_detection",
        "description": (
            "source_id로 지정한 원천 데이터 파일을 DuckDB로 직접 scan하여 숫자형 컬럼의 "
            "z-score 이상치를 탐지합니다. 전체 파일을 pandas DataFrame으로 적재하지 않습니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source_id": {
                    "type": "string",
                    "description": "이상치를 탐지할 원천 데이터 파일 source_id입니다.",
                },
                "column": {
                    "type": "string",
                    "description": "z-score 이상치 탐지에 사용할 숫자형 컬럼명입니다.",
                },
                "threshold": {
                    "type": "number",
                    "description": "이상치로 판단할 z-score 절댓값 기준입니다. 기본값은 3.0입니다.",
                },
                "limit": {
                    "type": "integer",
                    "description": "응답에 포함할 이상치 row 최대 개수입니다. 기본값은 100입니다.",
                },
            },
            "required": ["source_id", "column"],
            "additionalProperties": False,
        },
    }


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 DuckDB z-score 이상치를 탐지합니다."""
    source_id = read_string(arguments.get("source_id"))
    if source_id is None:
        return _error_result("source_id is required.")

    column = read_string(arguments.get("column"))
    if column is None:
        return _error_result("column is required.")

    threshold = _read_threshold(arguments.get("threshold"))
    if isinstance(threshold, str):
        return _error_result(threshold)

    try:
        limit = read_limit(arguments.get("limit") or 100)
        source_path = load_source_path(source_id)
        _validate_numeric_column(source_path, column)
        payload = detect_zscore_anomalies(
            source_path,
            column=column,
            threshold=threshold,
            limit=limit,
        )
    except KeyError:
        return _error_result("Source not found.")
    except ValueError as exc:
        return _error_result(str(exc))

    data = {
        "source_id": source_id,
        "column": column,
        "threshold": threshold,
        **payload,
    }
    return _success_result(data)


def detect_zscore_anomalies(
    source_path,
    *,
    column: str,
    threshold: float = 3.0,
    limit: int = 100,
) -> dict[str, object]:
    """DuckDB aggregate와 filter query로 전체 DataFrame 적재 없이 이상치를 탐지합니다."""
    value_expr = f"try_cast({quote_identifier(column)} AS DOUBLE)"
    stats = _load_column_statistics(source_path, value_expr)
    if stats["count"] == 0:
        raise ValueError(f"Column is not numeric or has no valid values: {column}")
    if stats["std"] == 0:
        return _build_payload(
            anomaly_count=0,
            anomalies=[],
            statistics=stats,
        )

    anomaly_count = _count_anomalies(
        source_path,
        value_expr=value_expr,
        mean=stats["mean"],
        std=stats["std"],
        threshold=threshold,
    )
    anomalies = _load_anomaly_rows(
        source_path,
        value_expr=value_expr,
        mean=stats["mean"],
        std=stats["std"],
        threshold=threshold,
        limit=limit,
    )
    return _build_payload(
        anomaly_count=anomaly_count,
        anomalies=anomalies,
        statistics=stats,
    )


def _load_column_statistics(source_path, value_expr: str) -> dict[str, float | int]:
    """DuckDB aggregate로 z-score 계산에 필요한 컬럼 통계를 조회합니다."""
    result = execute_dataset_sql(
        source_path,
        f"""
        SELECT
            count(value) AS count,
            avg(value) AS mean,
            stddev_samp(value) AS std,
            min(value) AS min,
            max(value) AS max
        FROM (
            SELECT {value_expr} AS value
            FROM dataset
        ) AS typed
        WHERE value IS NOT NULL
        """,
    )
    row = result.iloc[0].to_dict()
    return {
        "count": int(row.get("count") or 0),
        "mean": _to_json_float(row.get("mean")),
        "std": _to_json_float(row.get("std")),
        "min": _to_json_float(row.get("min")),
        "max": _to_json_float(row.get("max")),
    }


def _count_anomalies(
    source_path,
    *,
    value_expr: str,
    mean: float,
    std: float,
    threshold: float,
) -> int:
    """threshold를 넘는 이상치 row 수를 DuckDB에서 집계합니다."""
    result = execute_dataset_sql(
        source_path,
        f"""
        SELECT count(*) AS anomaly_count
        FROM (
            SELECT abs(({value_expr} - {mean}) / {std}) AS zscore
            FROM dataset
        ) AS scored
        WHERE zscore > {threshold}
        """,
    )
    row = result.iloc[0].to_dict()
    return int(row.get("anomaly_count") or 0)


def _load_anomaly_rows(
    source_path,
    *,
    value_expr: str,
    mean: float,
    std: float,
    threshold: float,
    limit: int,
) -> list[dict[str, int | float]]:
    """상위 이상치 row만 DuckDB에서 제한 조회합니다."""
    result = execute_dataset_sql(
        source_path,
        f"""
        WITH scored AS (
            SELECT
                row_number() OVER () - 1 AS row_index,
                {value_expr} AS value,
                abs(({value_expr} - {mean}) / {std}) AS zscore
            FROM dataset
        )
        SELECT row_index AS "index", value, zscore
        FROM scored
        WHERE value IS NOT NULL AND zscore > {threshold}
        ORDER BY zscore DESC
        LIMIT {limit}
        """,
    )
    rows: list[dict[str, int | float]] = []
    for row in result.to_dict("records"):
        rows.append(
            {
                "index": int(row["index"]),
                "value": _to_json_float(row.get("value")),
                "zscore": _to_json_float(row.get("zscore")),
            }
        )
    return rows


def _build_payload(
    *,
    anomaly_count: int,
    anomalies: list[dict[str, int | float]],
    statistics: dict[str, float | int],
) -> dict[str, object]:
    """이상치 결과를 LLM이 읽기 쉬운 payload로 변환합니다."""
    return {
        "anomaly_count": anomaly_count,
        "anomaly_indices": [row["index"] for row in anomalies],
        "anomalies": anomalies,
        "statistics": statistics,
    }


def _validate_numeric_column(source_path, column: str) -> None:
    """요청 컬럼이 DuckDB 기준 숫자형 컬럼인지 확인합니다."""
    numeric_columns = list_numeric_columns(source_path)
    if column not in numeric_columns:
        raise ValueError(f"Unknown or non-numeric column: {column}")


def _read_threshold(value: object) -> float | str:
    """선택 입력인 threshold를 양수 float으로 정규화합니다."""
    if value is None:
        return 3.0
    if isinstance(value, bool) or not isinstance(value, int | float):
        return "threshold must be a number."

    threshold = float(value)
    if threshold <= 0:
        return "threshold must be greater than 0."
    return threshold


def _to_json_float(value: object) -> float:
    """DuckDB numeric 결과를 JSON 안전 float으로 변환합니다."""
    if value is None:
        return 0.0
    number = float(value)
    return number if math.isfinite(number) else 0.0


def _success_result(data: dict[str, Any]) -> dict[str, object]:
    """이상치 탐지 성공 결과를 공통 DTO 형식으로 반환합니다."""
    return ToolExecutionResult[dict[str, Any]](ok=True, data=data).model_dump(
        mode="json",
        exclude_none=True,
    )


def _error_result(message: str) -> dict[str, object]:
    """이상치 탐지 실패 결과를 공통 DTO 형식으로 반환합니다."""
    return ToolExecutionResult[object](ok=False, error=message).model_dump(
        mode="json",
        exclude_none=True,
    )
