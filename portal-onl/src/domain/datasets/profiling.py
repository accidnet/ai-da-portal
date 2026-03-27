from __future__ import annotations

import pandas as pd

from domain.shared import DatasetColumnProfile, DatasetProfilePayload


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
        suggested_prompts=_build_suggested_prompts(dataframe),
    )


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


def _build_suggested_prompts(dataframe: pd.DataFrame) -> list[str]:
    numeric_columns = [
        str(column)
        for column in dataframe.columns
        if pd.api.types.is_numeric_dtype(dataframe[column])
    ]
    datetime_columns = [
        str(column)
        for column in dataframe.columns
        if pd.api.types.is_datetime64_any_dtype(dataframe[column])
    ]
    categorical_columns = [
        str(column)
        for column in dataframe.columns
        if not pd.api.types.is_numeric_dtype(dataframe[column])
    ]

    prompts: list[str] = []
    if numeric_columns:
        prompts.append(f"Compare trends in {numeric_columns[0]} across time or groups.")
    if datetime_columns and numeric_columns:
        prompts.append(f"Plot {numeric_columns[0]} over {datetime_columns[0]} and highlight anomalies.")
    if categorical_columns and numeric_columns:
        prompts.append(
            f"Aggregate {numeric_columns[0]} by {categorical_columns[0]} and explain the top segments."
        )
    if len(prompts) < 3:
        prompts.append("Summarize missing values and outlier risk in this dataset.")
    return prompts[:3]
