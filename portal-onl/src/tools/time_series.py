import pandas as pd


def build_time_series(
    df: pd.DataFrame, date_column: str, value_column: str
) -> list[dict[str, str | float]]:
    series = df[[date_column, value_column]].copy()
    series[date_column] = pd.to_datetime(series[date_column], errors="coerce")
    grouped = series.dropna().groupby(date_column, as_index=False)[value_column].sum()
    return [
        {
            date_column: row[date_column].isoformat(),
            value_column: float(row[value_column]),
        }
        for _, row in grouped.iterrows()
    ]
