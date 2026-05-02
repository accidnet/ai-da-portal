from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from .dto import DatasetColumnProfile, DatasetPreviewPayload, DatasetProfilePayload


def build_preview_from_dataframe(
    dataframe: pd.DataFrame, max_rows: int = 10, max_columns: int = 20
) -> DatasetPreviewPayload:
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
    columns = [
        DatasetColumnProfile(
            name=str(column),
            dtype=_normalize_dtype(dataframe[column]),
            null_ratio=_null_ratio(dataframe[column]),
            sample_values=_sample_values(dataframe[column]),
        )
        for column in dataframe.columns
    ]
    return DatasetProfilePayload(
        row_count=int(len(dataframe)),
        column_count=int(len(dataframe.columns)),
        columns=columns,
    )


def _coerce_preview_value(value: object) -> str | int | float | None:
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


def _normalize_dtype(series: pd.Series) -> str:
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
    if len(series) == 0:
        return 0.0
    return round(float(series.isna().mean()), 4)


def _sample_values(series: pd.Series, max_samples: int = 3) -> list[str]:
    samples: list[str] = []
    for value in series.dropna().head(max_samples):
        if hasattr(value, "isoformat"):
            samples.append(value.isoformat())
        else:
            samples.append(str(value))
    return samples
