from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi import UploadFile

from core.config import get_settings
from domain.datasets.preview import build_preview_from_dataframe
from domain.datasets.profiling import build_profile_from_dataframe
from domain.datasets.schemas import (
    DatasetDetail,
    DatasetPreviewResponse,
    DatasetProfileResponse,
)
from infrastructure.storage.files import save_upload_file


class DatasetService:
    def __init__(self) -> None:
        self._datasets: dict[str, _DatasetRecord] = {}

    async def upload(self, file: UploadFile) -> DatasetDetail:
        settings = get_settings()
        dataset_id = str(uuid4())
        suffix = Path(file.filename or "dataset.csv").suffix
        storage_path = f"{settings.uploads_dir}/{dataset_id}{suffix}"
        await save_upload_file(file=file, destination=Path(storage_path))

        dataframe = self._load_dataframe(Path(storage_path), suffix=suffix)
        detail = DatasetDetail(
            id=dataset_id,
            filename=file.filename or "dataset.csv",
            content_type=file.content_type,
            storage_path=storage_path,
            created_at=datetime.now(UTC),
        )
        self._datasets[dataset_id] = _DatasetRecord(detail=detail, dataframe=dataframe)

        return detail

    def list_datasets(self) -> list[DatasetDetail]:
        return sorted(
            (record.detail for record in self._datasets.values()),
            key=lambda detail: detail.created_at,
            reverse=True,
        )

    def get(self, dataset_id: str) -> DatasetDetail:
        return self._get_record(dataset_id).detail

    def get_profile(self, dataset_id: str) -> DatasetProfileResponse:
        record = self._get_record(dataset_id)
        return DatasetProfileResponse(
            dataset_id=dataset_id,
            profile=build_profile_from_dataframe(record.dataframe),
        )

    def get_preview(self, dataset_id: str) -> DatasetPreviewResponse:
        record = self._get_record(dataset_id)
        columns, rows = build_preview_from_dataframe(record.dataframe)
        return DatasetPreviewResponse(dataset_id=dataset_id, columns=columns, rows=rows)

    def get_dataframe(self, dataset_id: str) -> pd.DataFrame:
        return self._get_record(dataset_id).dataframe.copy()

    def get_latest_dataset_id(self) -> str | None:
        if not self._datasets:
            return None
        return max(self._datasets.values(), key=lambda record: record.detail.created_at).detail.id

    def _get_record(self, dataset_id: str) -> "_DatasetRecord":
        record = self._datasets.get(dataset_id)
        if record is None:
            raise KeyError(dataset_id)
        return record

    def _load_dataframe(self, path: Path, suffix: str) -> pd.DataFrame:
        normalized_suffix = suffix.lower()
        if normalized_suffix in {".csv", ".txt"}:
            dataframe = pd.read_csv(path)
        if normalized_suffix in {".tsv"}:
            dataframe = pd.read_csv(path, sep="\t")
        if normalized_suffix in {".xlsx", ".xls"}:
            dataframe = pd.read_excel(path)
        if normalized_suffix in {".json"}:
            dataframe = pd.read_json(path)
        if normalized_suffix not in {".csv", ".txt", ".tsv", ".xlsx", ".xls", ".json"}:
            dataframe = pd.read_csv(path)
        return self._infer_datetime_columns(dataframe)

    def _infer_datetime_columns(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        inferred = dataframe.copy()
        for column in inferred.columns:
            series = inferred[column]
            if not pd.api.types.is_object_dtype(series):
                continue
            converted = pd.to_datetime(series, errors="coerce", format="mixed")
            if converted.notna().mean() >= 0.8 and converted.notna().any():
                inferred[column] = converted
        return inferred


@dataclass(slots=True)
class _DatasetRecord:
    detail: DatasetDetail
    dataframe: pd.DataFrame
