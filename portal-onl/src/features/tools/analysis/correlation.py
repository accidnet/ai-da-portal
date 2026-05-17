from typing import Any

import pandas as pd

from core.utils import read_string
from features.tools.analysis.dataframe_context import load_dataset_dataframe
from features.tools.dto import ToolExecutionResult


def tool_definition() -> dict[str, object]:
    """상관관계 분석용 에이전트 tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "correlation",
        "description": (
            "선택한 데이터셋의 숫자형 컬럼 간 상관계수 행렬을 계산합니다. "
            "상관관계 수치가 필요한 질문에 사용합니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "string",
                    "description": "상관관계를 계산할 데이터셋 ID입니다.",
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "선택적으로 상관관계 계산에 포함할 컬럼 목록입니다.",
                },
            },
            "required": ["dataset_id"],
            "additionalProperties": False,
        },
    }


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 상관관계 행렬을 계산합니다."""
    dataset_id = read_string(arguments.get("dataset_id"))
    if dataset_id is None:
        return _error_result("dataset_id is required.")

    selected_columns = _read_columns(arguments.get("columns"))
    if isinstance(selected_columns, str):
        return _error_result(selected_columns)

    try:
        dataframe = load_dataset_dataframe(dataset_id)
        matrix = compute_correlation_matrix(dataframe, columns=selected_columns)
    except KeyError:
        return _error_result("Dataset not found.")
    except ValueError as exc:
        return _error_result(str(exc))

    data = {
        "dataset_id": dataset_id,
        "columns": list(matrix.keys()),
        "correlation_matrix": matrix,
    }
    return _success_result(data)


def compute_correlation_matrix(
    dataframe: pd.DataFrame,
    *,
    columns: list[str] | None = None,
) -> dict[str, dict[str, float]]:
    """DataFrame의 숫자형 컬럼 상관계수 행렬을 계산합니다."""
    target = _select_columns(dataframe, columns)
    numeric_dataframe = target.select_dtypes(include=["number"])
    if numeric_dataframe.empty:
        raise ValueError("No numeric columns are available for correlation.")
    if len(numeric_dataframe.columns) < 2:
        raise ValueError("At least two numeric columns are required for correlation.")

    # NaN은 LLM이 JSON으로 안정적으로 읽을 수 있도록 0.0으로 치환합니다.
    return _to_float_matrix(numeric_dataframe.corr(numeric_only=True).fillna(0.0))


def _select_columns(
    dataframe: pd.DataFrame,
    columns: list[str] | None,
) -> pd.DataFrame:
    """요청된 컬럼이 있으면 해당 컬럼만 선택합니다."""
    if not columns:
        return dataframe

    missing = [column for column in columns if column not in dataframe.columns]
    if missing:
        raise ValueError(f"Unknown columns: {', '.join(missing)}")
    return dataframe[columns]


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


def _to_float_matrix(dataframe: pd.DataFrame) -> dict[str, dict[str, float]]:
    """pandas corr 결과를 JSON 직렬화에 적합한 float dict로 변환합니다."""
    matrix: dict[str, dict[str, float]] = {}
    for row_name, row in dataframe.to_dict().items():
        matrix[str(row_name)] = {
            str(column): float(value) for column, value in row.items()
        }
    return matrix


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
