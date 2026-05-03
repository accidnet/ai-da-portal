from typing import Any

import pandas as pd

from core.utils import read_string
from tools.analysis.dataframe_context import load_dataset_dataframe
from tools.dto import ToolExecutionResult


def tool_definition() -> dict[str, object]:
    """이상치 탐지용 에이전트 tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "anomaly_detection",
        "description": (
            "선택한 데이터셋의 숫자형 컬럼에서 z-score 기준 이상치를 탐지합니다. "
            "특정 컬럼의 극단값이나 이상 행을 확인할 때 사용합니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "string",
                    "description": "이상치를 탐지할 데이터셋 ID입니다.",
                },
                "column": {
                    "type": "string",
                    "description": "z-score 이상치 탐지에 사용할 숫자형 컬럼명입니다.",
                },
                "threshold": {
                    "type": "number",
                    "description": "이상치로 판단할 z-score 절댓값 기준입니다. 기본값은 3.0입니다.",
                },
            },
            "required": ["dataset_id", "column"],
            "additionalProperties": False,
        },
    }


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 z-score 이상치를 탐지합니다."""
    dataset_id = read_string(arguments.get("dataset_id"))
    if dataset_id is None:
        return _error_result("dataset_id is required.")

    column = read_string(arguments.get("column"))
    if column is None:
        return _error_result("column is required.")

    threshold = _read_threshold(arguments.get("threshold"))
    if isinstance(threshold, str):
        return _error_result(threshold)

    try:
        dataframe = load_dataset_dataframe(dataset_id)
        payload = detect_zscore_anomalies(
            dataframe,
            column=column,
            threshold=threshold,
        )
    except KeyError:
        return _error_result("Dataset not found.")
    except ValueError as exc:
        return _error_result(str(exc))

    data = {
        "dataset_id": dataset_id,
        "column": column,
        "threshold": threshold,
        **payload,
    }
    return _success_result(data)


def detect_zscore_anomalies(
    dataframe: pd.DataFrame,
    *,
    column: str,
    threshold: float = 3.0,
) -> dict[str, object]:
    """DataFrame의 단일 숫자형 컬럼에서 z-score 이상치를 탐지합니다."""
    if column not in dataframe.columns:
        raise ValueError(f"Unknown column: {column}")

    series = pd.to_numeric(dataframe[column], errors="coerce").dropna()
    if series.empty:
        raise ValueError(f"Column is not numeric or has no valid values: {column}")

    standard_deviation = float(series.std())
    if standard_deviation == 0:
        return _build_anomaly_payload(series=series, zscores=pd.Series(dtype=float))

    zscores = ((series - float(series.mean())) / standard_deviation).abs()
    anomalies = zscores[zscores > threshold]
    return _build_anomaly_payload(series=series, zscores=anomalies)


def _build_anomaly_payload(
    *,
    series: pd.Series,
    zscores: pd.Series,
) -> dict[str, object]:
    """이상치 index와 값을 LLM이 읽기 쉬운 payload로 변환합니다."""
    anomaly_rows = [
        {
            "index": int(index) if isinstance(index, int) else str(index),
            "value": _to_builtin_number(series.loc[index]),
            "zscore": float(zscore),
        }
        for index, zscore in zscores.items()
    ]
    return {
        "anomaly_count": len(anomaly_rows),
        "anomaly_indices": [row["index"] for row in anomaly_rows],
        "anomalies": anomaly_rows,
        "statistics": {
            "count": int(series.count()),
            "mean": float(series.mean()),
            "std": float(series.std()),
            "min": _to_builtin_number(series.min()),
            "max": _to_builtin_number(series.max()),
        },
    }


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


def _to_builtin_number(value: object) -> int | float:
    """numpy scalar 값을 JSON 직렬화 가능한 숫자로 변환합니다."""
    number = float(value)
    return int(number) if number.is_integer() else number


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
