import pandas as pd


def compute_correlation_matrix(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    numeric_df = df.select_dtypes(include=["number"])
    if numeric_df.empty:
        return {}
    return numeric_df.corr(numeric_only=True).fillna(0.0).to_dict()
