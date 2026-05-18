from pathlib import Path

import duckdb
import pandas as pd

from features.datasets.application.dto import DatasetPreviewPayload, DatasetProfilePayload
from features.datasets.application.inspection import (
    build_preview_from_dataframe,
    build_profile_from_dataframe,
)


PROFILE_SAMPLE_ROWS = 5_000
LINE_COUNT_CHUNK_SIZE = 1024 * 1024
DUCKDB_SAMPLE_SUFFIXES = {".csv", ".txt", ".tsv", ".json", ".parquet"}
DUCKDB_COUNT_SUFFIXES = {".json", ".parquet"}


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
    if suffix in DUCKDB_SAMPLE_SUFFIXES:
        try:
            return _load_sample_dataframe_with_duckdb(path)
        except duckdb.Error:
            # DuckDB가 특정 CSV dialect를 처리하지 못하면 기존 pandas 샘플 로드로 보완합니다.
            if suffix not in {".csv", ".txt", ".tsv"}:
                raise
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
    """CSV/TSV 행 수는 파싱 없이 라인 수로 계산하고 그 외 형식은 샘플 행 수를 사용합니다."""
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt", ".tsv"}:
        return _count_delimited_file_rows(path, fallback_count=fallback_count)
    if suffix in DUCKDB_COUNT_SUFFIXES:
        return _count_rows_with_duckdb(path, fallback_count=fallback_count)
    return fallback_count


def _load_sample_dataframe_with_duckdb(path: Path) -> pd.DataFrame:
    """DuckDB로 원천 파일을 직접 스캔해 작은 샘플 DataFrame만 가져옵니다."""
    connection = duckdb.connect(database=":memory:")
    try:
        scan_expression = _build_duckdb_scan_expression(path)
        return connection.execute(
            f"SELECT * FROM {scan_expression} LIMIT {PROFILE_SAMPLE_ROWS}"
        ).fetchdf()
    finally:
        connection.close()


def _count_rows_with_duckdb(path: Path, *, fallback_count: int) -> int:
    """DuckDB가 효율적으로 처리할 수 있는 파일 형식의 전체 행 수를 계산합니다."""
    connection = duckdb.connect(database=":memory:")
    try:
        scan_expression = _build_duckdb_scan_expression(path)
        result = connection.execute(
            f"SELECT COUNT(*) AS row_count FROM {scan_expression}"
        ).fetchone()
    except duckdb.Error:
        return fallback_count
    finally:
        connection.close()
    if result is None:
        return fallback_count
    return int(result[0])


def _count_delimited_file_rows(path: Path, *, fallback_count: int) -> int:
    """대용량 CSV/TSV를 DataFrame으로 다시 읽지 않고 헤더를 제외한 라인 수를 계산합니다."""
    line_count = 0
    last_byte = b""
    try:
        with path.open("rb") as file:
            while chunk := file.read(LINE_COUNT_CHUNK_SIZE):
                line_count += chunk.count(b"\n")
                last_byte = chunk[-1:]
    except OSError:
        return fallback_count

    if line_count == 0:
        return fallback_count

    # 마지막 줄이 개행으로 끝나지 않은 파일도 마지막 데이터 행을 누락하지 않도록 보정합니다.
    if last_byte not in {b"", b"\n", b"\r"}:
        line_count += 1
    return max(line_count - 1, 0)


def _build_duckdb_scan_expression(path: Path) -> str:
    """파일 확장자에 맞는 DuckDB scan expression을 생성합니다."""
    suffix = path.suffix.lower()
    path_literal = _duckdb_string_literal(str(path))
    if suffix in {".csv", ".txt"}:
        return f"read_csv_auto({path_literal}, sample_size={PROFILE_SAMPLE_ROWS})"
    if suffix == ".tsv":
        return (
            f"read_csv_auto({path_literal}, delim='\\t', "
            f"sample_size={PROFILE_SAMPLE_ROWS})"
        )
    if suffix == ".json":
        return f"read_json_auto({path_literal})"
    if suffix == ".parquet":
        return f"read_parquet({path_literal})"
    raise ValueError(f"Unsupported dataset format for DuckDB profiling: {suffix}")


def _duckdb_string_literal(value: str) -> str:
    """DuckDB SQL에 삽입할 문자열 literal을 안전하게 생성합니다."""
    return f"'{value.replace("'", "''")}'"
