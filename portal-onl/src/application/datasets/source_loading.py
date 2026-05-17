from pathlib import Path

import pandas as pd

from application.datasets.dataframe_loader import load_dataframe
from application.datasets.ports import DatasetMetadataRecord
from core.paths import UPLOADED_DATASET_DIR
from features.data_sources.infrastructure.repositories import DataSourceRepository


def resolve_dataset_source_paths(
    dataset: DatasetMetadataRecord,
    data_source_repository: DataSourceRepository | None = None,
) -> list[tuple[str, Path]]:
    """데이터셋 정의에서 실제 읽을 수 있는 원천 파일 경로 목록을 복원합니다."""
    paths: list[tuple[str, Path]] = []
    source_ref_ids = [
        source.source_ref_id
        for source in dataset.sources
        if source.source_ref_id is not None
    ]
    if source_ref_ids:
        repository = data_source_repository or DataSourceRepository()
        for item in repository.list_items_by_ids(source_ref_ids):
            if item.storage_path is not None:
                paths.append((item.relative_path, Path(item.storage_path)))
        return paths

    storage_path = dataset.storage_path
    if storage_path is not None:
        return [(dataset.filename, Path(storage_path))]

    direct_upload_path = _resolve_direct_upload_path(dataset)
    if direct_upload_path is not None:
        return [(dataset.filename, direct_upload_path)]
    return []


def load_dataset_dataframes(
    dataset: DatasetMetadataRecord,
    data_source_repository: DataSourceRepository | None = None,
) -> list[tuple[str, pd.DataFrame]]:
    """데이터셋의 원천 파일들을 DataFrame 목록으로 로드합니다."""
    frames: list[tuple[str, pd.DataFrame]] = []
    for source_path, path in resolve_dataset_source_paths(dataset, data_source_repository):
        frames.append((source_path, load_dataframe(path)))
    return frames


def load_dataset_dataframe(
    dataset: DatasetMetadataRecord,
    data_source_repository: DataSourceRepository | None = None,
) -> pd.DataFrame:
    """단일 데이터셋의 원천 파일을 합쳐 하나의 DataFrame으로 로드합니다."""
    dataframes = load_dataset_dataframes(dataset, data_source_repository)
    if not dataframes:
        raise ValueError("Dataset has no readable source files.")

    frames: list[pd.DataFrame] = []
    for source_path, dataframe in dataframes:
        frame = dataframe.copy()
        if len(dataframes) > 1:
            frame["__source_path"] = source_path
        frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False)


def _resolve_direct_upload_path(dataset: DatasetMetadataRecord) -> Path | None:
    """직접 업로드 데이터셋의 저장 파일 경로를 dataset id와 파일명 규칙으로 찾습니다."""
    safe_name = Path(dataset.filename).name
    if not safe_name:
        return None

    expected_path = UPLOADED_DATASET_DIR / f"{dataset.id}__{safe_name}"
    if expected_path.is_file():
        return expected_path

    matches = sorted(UPLOADED_DATASET_DIR.glob(f"{dataset.id}__*"))
    return matches[0] if matches else None
