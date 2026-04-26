from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi import UploadFile

from domain.datasets.preview import build_preview_from_dataframe
from domain.datasets.profiling import build_profile_from_dataframe
from domain.datasets.schemas import (
    DatasetDeleteResponse,
    DatasetDetail,
    DatasetPreviewResponse,
    DatasetProfileResponse,
    DatasetSummary,
)
from domain.sessions.service import SessionService


class DatasetService:
    def __init__(self, session_service: SessionService | None = None) -> None:
        self._datasets: dict[str, _DatasetRecord] = {}
        self._session_service = session_service

    async def upload(
        self, file: UploadFile, session_id: str | None = None
    ) -> DatasetDetail:
        # dataset 고유 id 부여
        dataset_id = str(uuid4())

        # filename 추출
        filename = file.filename or "dataset.csv"

        # suffix 추출
        suffix = Path(filename).suffix

        # file 읽기
        content = await file.read()

        # dataframe으로 변환
        dataframe = self._load_dataframe(content, suffix=suffix)
        detail = DatasetDetail(
            id=dataset_id,
            filename=file.filename or "dataset.csv",
            content_type=file.content_type,
            storage_path=None,
            created_at=datetime.now(UTC),
        )
        self._datasets[dataset_id] = _DatasetRecord(detail=detail, dataframe=dataframe)

        if session_id is not None and self._session_service is not None:
            self._session_service.attach_dataset(
                session_id,
                dataset_id,
                title=file.filename or "Uploaded dataset",
            )

        return detail

    def list_datasets(self) -> list[DatasetSummary]:
        return sorted(
            (self._build_summary(record) for record in self._datasets.values()),
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
        return max(
            self._datasets.values(), key=lambda record: record.detail.created_at
        ).detail.id

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
        linked_sessions = self._linked_sessions(record.detail.id)
        linked_session_ids = [session_id for session_id, _ in linked_sessions]
        latest_used_at = linked_sessions[0][1] if linked_sessions else None
        return DatasetSummary(
            **record.detail.model_dump(),
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
    detail: DatasetDetail
    dataframe: pd.DataFrame
