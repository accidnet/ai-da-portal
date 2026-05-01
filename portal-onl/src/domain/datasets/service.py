from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi import UploadFile

from core.paths import UPLOADED_DATASET_DIR
from domain.datasets.preview import build_preview_from_dataframe
from domain.datasets.profiling import build_profile_from_dataframe
from domain.datasets.schemas import (
    DatasetDeleteResponse,
    DatasetInfo,
    DatasetPreviewResponse,
    DatasetProfileResponse,
    DatasetSummary,
)
from domain.sessions.service import SessionService
from tools.dataframe_loader import load_dataframe


class DatasetService:
    def __init__(self, session_service: SessionService | None = None) -> None:
        self._datasets: dict[str, _DatasetRecord] = {}
        self._session_service = session_service

    async def upload(self, file: UploadFile) -> DatasetInfo:
        # dataset 고유 id 부여
        dataset_id = str(uuid4())

        # filename 추출
        filename = file.filename or "dataset.csv"

        # suffix 추출
        suffix = Path(filename).suffix

        # file 읽기
        content = await file.read()

        # file 저장
        storage_path = self._store_uploaded_file(dataset_id, filename, content)

        # dataframe으로 변환
        dataframe = self._load_dataframe(content, suffix=suffix)

        # Dataset 기본 정보
        dataset_info = DatasetInfo(
            id=dataset_id,
            filename=file.filename or "dataset.csv",
            storage_path=str(storage_path),
            created_at=datetime.now(UTC),
        )

        # 클래스 변수에 할당
        self._datasets[dataset_id] = _DatasetRecord(
            dataset_info=dataset_info,
            dataframe=dataframe,
        )

        return dataset_info

    def list_datasets(self) -> list[DatasetSummary]:
        return sorted(
            (self._build_summary(record) for record in self._datasets.values()),
            key=lambda detail: detail.created_at,
            reverse=True,
        )

    def get(self, dataset_id: str) -> DatasetInfo:
        return self._get_record(dataset_id).dataset_info

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
        return max(
            self._datasets.values(), key=lambda record: record.dataset_info.created_at
        ).dataset_info.id

    def get_uploaded_filenames(self, dataset_ids: list[str]) -> list[str]:
        filenames: list[str] = []
        for dataset_id in dataset_ids:
            record = self._datasets.get(dataset_id)
            if record is None:
                continue
            filename = record.dataset_info.filename
            if filename not in filenames:
                filenames.append(filename)
        return filenames

    def load_uploaded_file_by_filename(self, filename: str) -> dict[str, object]:
        normalized_filename = Path(filename).name
        record = self._find_record_by_filename(normalized_filename)
        if record is None or record.dataset_info.storage_path is None:
            raise FileNotFoundError(normalized_filename)

        storage_path = Path(record.dataset_info.storage_path)
        dataframe = self._infer_datetime_columns(load_dataframe(storage_path))
        preview = build_preview_from_dataframe(dataframe)

        return {
            "filename": normalized_filename,
            "dataset_id": record.dataset_info.id,
            "storage_path": str(storage_path),
            "row_count": int(len(dataframe.index)),
            "column_count": int(len(dataframe.columns)),
            "columns": [str(column) for column in dataframe.columns.tolist()],
            "dtypes": {
                str(column): str(dtype)
                for column, dtype in dataframe.dtypes.astype(str).items()
            },
            "null_counts": {
                str(column): int(count)
                for column, count in dataframe.isna().sum().items()
            },
            "preview": {
                "columns": preview[0],
                "rows": preview[1],
            },
        }

    def delete(self, dataset_id: str) -> DatasetDeleteResponse:
        linked_sessions = self._linked_sessions(dataset_id)
        if linked_sessions:
            raise ValueError("Dataset is still linked to one or more sessions.")
        del self._datasets[dataset_id]
        return DatasetDeleteResponse(id=dataset_id, deleted=True)

    def _get_record(self, dataset_id: str) -> "_DatasetRecord":
        record = self._datasets.get(dataset_id)
        if record is None:
            raise KeyError(dataset_id)
        return record

    def _build_summary(self, record: "_DatasetRecord") -> DatasetSummary:
        linked_sessions = self._linked_sessions(record.dataset_info.id)
        linked_session_ids = [session_id for session_id, _ in linked_sessions]
        latest_used_at = linked_sessions[0][1] if linked_sessions else None
        return DatasetSummary(
            **record.dataset_info.model_dump(),
            row_count=len(record.dataframe.index),
            column_count=len(record.dataframe.columns),
            linked_session_count=len(linked_session_ids),
            linked_session_ids=linked_session_ids,
            latest_used_at=latest_used_at,
        )

    def _linked_sessions(self, dataset_id: str) -> list[tuple[str, datetime]]:
        if self._session_service is None:
            return []
        return self._session_service.list_linked_sessions(dataset_id)

    def _store_uploaded_file(
        self, dataset_id: str, filename: str, content: bytes
    ) -> Path:
        UPLOADED_DATASET_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name or "dataset.csv"
        stored_path = UPLOADED_DATASET_DIR / f"{dataset_id}__{safe_name}"
        stored_path.write_bytes(content)
        return stored_path

    def _find_record_by_filename(self, filename: str) -> "_DatasetRecord | None":
        candidates = [
            record
            for record in self._datasets.values()
            if record.dataset_info.filename == filename and record.dataset_info.storage_path is not None
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda record: record.dataset_info.created_at)

    def _load_dataframe(self, content: bytes, suffix: str) -> pd.DataFrame:
        normalized_suffix = suffix.lower()
        buffer = BytesIO(content)
        if normalized_suffix in {".csv", ".txt"}:
            dataframe = pd.read_csv(buffer)
        if normalized_suffix in {".tsv"}:
            buffer.seek(0)
            dataframe = pd.read_csv(buffer, sep="\t")
        if normalized_suffix in {".xlsx", ".xls"}:
            buffer.seek(0)
            dataframe = pd.read_excel(buffer)
        if normalized_suffix in {".json"}:
            buffer.seek(0)
            dataframe = pd.read_json(buffer)
        if normalized_suffix not in {".csv", ".txt", ".tsv", ".xlsx", ".xls", ".json"}:
            buffer.seek(0)
            dataframe = pd.read_csv(buffer)
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
    dataset_info: DatasetInfo
    dataframe: pd.DataFrame
