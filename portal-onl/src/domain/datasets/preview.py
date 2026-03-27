from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def build_preview_from_dataframe(
    dataframe: pd.DataFrame, max_rows: int = 10
) -> tuple[list[str], list[dict[str, str | int | float | None]]]:
    columns = [str(column) for column in dataframe.columns]
    preview_frame = dataframe.head(max_rows).copy()
    preview_frame = preview_frame.where(pd.notna(preview_frame), None)
    rows = [
        {
            key: _coerce_preview_value(value)
            for key, value in row.items()
        }
        for row in preview_frame.to_dict(orient="records")
    ]
    return columns, rows


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
