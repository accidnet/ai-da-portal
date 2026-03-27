import pandas as pd


def detect_zscore_anomalies(
    df: pd.DataFrame, column: str, threshold: float = 3.0
) -> list[int]:
    series = df[column].dropna()
    if series.empty or series.std() == 0:
        return []
    zscores = ((series - series.mean()) / series.std()).abs()
    return [int(index) for index in zscores[zscores > threshold].index.tolist()]
