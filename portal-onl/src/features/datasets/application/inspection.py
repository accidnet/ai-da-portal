from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from .dto import (
    DatasetColumnProfile,
    DatasetPreviewPayload,
    DatasetProfilePayload,
    DatasetProfileValue,
)


def build_preview_from_dataframe(
    dataframe: pd.DataFrame, max_rows: int = 10, max_columns: int = 20
) -> DatasetPreviewPayload:
    """DataFrame의 앞부분을 화면 미리보기 payload로 변환합니다."""
    preview_columns = list(dataframe.columns[:max_columns])
    columns = [str(column) for column in preview_columns]
    preview_frame = dataframe.loc[:, preview_columns].head(max_rows).copy()
    preview_frame = preview_frame.where(pd.notna(preview_frame), None)
    rows = [
        {key: _coerce_preview_value(value) for key, value in row.items()}
        for row in preview_frame.to_dict(orient="records")
    ]
    return DatasetPreviewPayload(columns=columns, rows=rows)


def build_profile_from_dataframe(dataframe: pd.DataFrame) -> DatasetProfilePayload:
    """DataFrame 전체 컬럼의 타입과 품질 요약 profile을 생성합니다."""
    columns = [
        _build_column_profile(str(column), dataframe[column])
        for column in dataframe.columns
    ]
    return DatasetProfilePayload(
        row_count=int(len(dataframe)),
        column_count=int(len(dataframe.columns)),
        columns=columns,
    )


def _build_column_profile(name: str, series: pd.Series) -> DatasetColumnProfile:
    """컬럼별 타입, 품질, 범위 정보를 하나의 프로파일 항목으로 구성합니다."""
    min_value, max_value = _range_values(series)
    return DatasetColumnProfile(
        name=name,
        dtype=_normalize_dtype(series),
        null_ratio=_null_ratio(series),
        min_value=min_value,
        max_value=max_value,
        sample_values=_sample_values(series),
    )


def _coerce_preview_value(value: object) -> str | int | float | None:
    """미리보기 셀 값을 JSON 직렬화 가능한 값으로 변환합니다."""
    if value is None:
        return None
    if isinstance(value, (str, int, float)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, str)):
        return ", ".join(str(item) for item in value)
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _coerce_profile_value(value: object) -> DatasetProfileValue:
    """profile 범위 값을 JSON으로 직렬화 가능한 스칼라로 변환합니다."""
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, (str, int, float)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _normalize_dtype(series: pd.Series) -> str:
    """pandas dtype을 화면과 도구에서 쓰는 단순 타입명으로 정규화합니다."""
    dtype = str(series.dtype)
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_integer_dtype(series):
        return "int"
    if pd.api.types.is_float_dtype(series):
        return "float"
    if pd.api.types.is_bool_dtype(series):
        return "bool"
    if dtype.startswith("category"):
        return "category"
    return "string"


def _null_ratio(series: pd.Series) -> float:
    """컬럼의 결측 비율을 소수 네 자리까지 계산합니다."""
    if len(series) == 0:
        return 0.0
    return round(float(series.isna().mean()), 4)


def _range_values(series: pd.Series) -> tuple[DatasetProfileValue, DatasetProfileValue]:
    """숫자와 날짜 컬럼에서 분석에 유효한 최소/최대 범위를 계산합니다."""
    if pd.api.types.is_bool_dtype(series):
        return None, None
    if not (
        pd.api.types.is_numeric_dtype(series)
        or pd.api.types.is_datetime64_any_dtype(series)
    ):
        return None, None

    available = series.dropna()
    if available.empty:
        return None, None
    return _coerce_profile_value(available.min()), _coerce_profile_value(
        available.max()
    )


def _sample_values(series: pd.Series, max_samples: int = 3) -> list[str]:
    """프로파일에 표시할 대표 샘플 값을 문자열 목록으로 반환합니다."""
    samples: list[str] = []
    for value in series.dropna().head(max_samples):
        if hasattr(value, "isoformat"):
            samples.append(value.isoformat())
        else:
            samples.append(str(value))
    return samples
