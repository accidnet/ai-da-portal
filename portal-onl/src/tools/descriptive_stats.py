import pandas as pd


def summarize_dataframe(df: pd.DataFrame) -> dict[str, int | list[str]]:
    return {
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": [str(column) for column in df.columns],
    }
