from pathlib import Path

import pandas as pd


def load_dataframe(path: str | Path) -> pd.DataFrame:
    """업로드된 데이터셋 파일을 확장자에 맞춰 DataFrame으로 로드합니다."""
    path = Path(path)
    if path.suffix.lower() in {".csv", ".txt"}:
        return pd.read_csv(path)
    if path.suffix.lower() == ".tsv":
        return pd.read_csv(path, sep="\t")
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if path.suffix.lower() == ".json":
        return pd.read_json(path)
    raise ValueError(f"Unsupported dataset format: {path.suffix}")
