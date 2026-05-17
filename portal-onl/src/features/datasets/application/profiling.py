from pathlib import Path

import pandas as pd

from features.datasets.application.dto import DatasetPreviewPayload, DatasetProfilePayload
from features.datasets.application.inspection import (
    build_preview_from_dataframe,
    build_profile_from_dataframe,
)


PROFILE_SAMPLE_ROWS = 5_000
ROW_COUNT_CHUNK_SIZE = 100_000


def build_profile_snapshot_from_path(
    path: Path,
) -> tuple[DatasetPreviewPayload, DatasetProfilePayload]:
    """파일 전체를 메모리에 올리지 않고 데이터셋 preview/profile 스냅샷을 생성합니다."""
    sample = _load_sample_dataframe(path)
    sample = infer_datetime_columns(sample)
    preview = build_preview_from_dataframe(sample)
    profile = build_profile_from_dataframe(sample)
    row_count = _count_rows(path, fallback_count=len(sample.index))
    return preview, profile.model_copy(update={"row_count": row_count})


def infer_datetime_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """object 컬럼 중 날짜로 보이는 컬럼만 샘플 기준으로 datetime 타입으로 변환합니다."""
    inferred = dataframe.copy()
    for column in inferred.columns:
        series = inferred[column]
        if not pd.api.types.is_object_dtype(series):
            continue
        converted = pd.to_datetime(series, errors="coerce", format="mixed")
        if converted.notna().mean() >= 0.8 and converted.notna().any():
            inferred[column] = converted
    return inferred


def _load_sample_dataframe(path: Path) -> pd.DataFrame:
    """지원 파일을 profiling에 필요한 최대 행 수까지만 DataFrame으로 읽습니다."""
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(path, nrows=PROFILE_SAMPLE_ROWS)
    if suffix == ".tsv":
        return pd.read_csv(path, sep="\t", nrows=PROFILE_SAMPLE_ROWS)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, nrows=PROFILE_SAMPLE_ROWS)
    if suffix == ".json":
        return pd.read_json(path)
    raise ValueError(f"Unsupported dataset format: {path.suffix}")


def _count_rows(path: Path, *, fallback_count: int) -> int:
    """CSV/TSV 행 수는 청크 단위로 계산하고 그 외 형식은 샘플 행 수를 사용합니다."""
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt", ".tsv"}:
        separator = "\t" if suffix == ".tsv" else ","
        row_count = 0
        for chunk in pd.read_csv(path, sep=separator, chunksize=ROW_COUNT_CHUNK_SIZE):
            row_count += len(chunk.index)
        return row_count
    return fallback_count
