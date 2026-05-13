from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi import UploadFile

from application.datasets.dto import DatasetPreviewPayload, DatasetProfilePayload
from application.datasets.inspection import (
    build_preview_from_dataframe,
    build_profile_from_dataframe,
)
from core.paths import UPLOADED_DATASET_DIR
from domain.datasets.schemas import (
    DatasetDeleteResponse,
    DatasetInfo,
    DatasetPreviewResponse,
    DatasetProfileResponse,
    DatasetSummary,
)
from domain.sessions.service import SessionService
from infrastructure.db.models import DatasetOrm
from infrastructure.db.repositories import DatasetRepository
from tools.datasets.dataframe_loader import load_dataframe


class DatasetApplicationService:
    """업로드된 원천 데이터의 저장, 조회, 프로파일 생성을 담당합니다."""

    def __init__(
        self,
        dataset_repository: DatasetRepository,
        session_service: SessionService | None = None,
    ) -> None:
        self._dataset_repository = dataset_repository
        self._session_service = session_service

    async def upload(self, file: UploadFile) -> DatasetInfo:
        """원천 데이터 파일을 저장하고, 가능한 경우 표 형태 프로파일을 생성합니다."""
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

        # 표 형태로 읽을 수 없는 파일도 원천 데이터로 보관하기 위해 빈 프로파일을 사용합니다.
        try:
            dataframe = self._load_dataframe(content, suffix=suffix)
            preview = build_preview_from_dataframe(dataframe)
            profile = build_profile_from_dataframe(dataframe)
        except Exception:
            preview = DatasetPreviewPayload()
            profile = DatasetProfilePayload(row_count=0, column_count=0)

        # Dataset 기본 정보
        dataset = self._dataset_repository.create(
            dataset_id=dataset_id,
            filename=filename,
            storage_path=str(storage_path),
            preview=preview.model_dump(mode="json"),
            profile=profile.model_dump(mode="json"),
            created_at=datetime.now(UTC),
        )
        return self._to_dataset_info(dataset)

    def list_datasets(self) -> list[DatasetSummary]:
        return [
            self._build_summary(dataset)
            for dataset in self._dataset_repository.list_datasets()
        ]

    def get(self, dataset_id: str) -> DatasetInfo:
        return self._to_dataset_info(self._dataset_repository.get_or_raise(dataset_id))

    def get_profile(self, dataset_id: str) -> DatasetProfileResponse:
        dataset = self._dataset_repository.get_or_raise(dataset_id)
        profile = self._get_stored_profile(dataset)
        if profile is not None:
            return DatasetProfileResponse(dataset_id=dataset_id, profile=profile)
        return DatasetProfileResponse(
            dataset_id=dataset_id,
            profile=build_profile_from_dataframe(
                self._load_dataframe_from_dataset(dataset)
            ),
        )

    def get_preview(self, dataset_id: str) -> DatasetPreviewResponse:
        dataset = self._dataset_repository.get_or_raise(dataset_id)
        preview = self._get_stored_preview(dataset)
        if preview is None:
            preview = build_preview_from_dataframe(
                self._load_dataframe_from_dataset(dataset)
            )
        return DatasetPreviewResponse(
            dataset_id=dataset_id,
            columns=preview.columns,
            rows=preview.rows,
        )

    def get_dataframe(self, dataset_id: str) -> pd.DataFrame:
        dataset = self._dataset_repository.get_or_raise(dataset_id)
        return self._load_dataframe_from_dataset(dataset)

    def get_latest_dataset_id(self) -> str | None:
        dataset = self._dataset_repository.get_latest()
        return dataset.id if dataset is not None else None

    def get_uploaded_filenames(self, dataset_ids: list[str]) -> list[str]:
        filenames: list[str] = []
        for dataset_id in dataset_ids:
            dataset = self._dataset_repository.get(dataset_id)
            if dataset is None:
                continue
            filename = dataset.filename
            if filename not in filenames:
                filenames.append(filename)
        return filenames

    def load_uploaded_file_by_filename(self, filename: str) -> dict[str, object]:
        normalized_filename = Path(filename).name
        dataset = self._dataset_repository.find_latest_by_filename(normalized_filename)
        if dataset is None:
            raise FileNotFoundError(normalized_filename)

        storage_path = Path(dataset.storage_path)
        dataframe = self._load_dataframe_from_dataset(dataset)
        preview = build_preview_from_dataframe(dataframe)

        return {
            "filename": normalized_filename,
            "dataset_id": dataset.id,
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
                "columns": preview.columns,
                "rows": preview.rows,
            },
        }

    def delete(self, dataset_id: str) -> DatasetDeleteResponse:
        linked_sessions = self._linked_sessions(dataset_id)
        if linked_sessions:
            raise ValueError("Dataset is still linked to one or more sessions.")
        self._dataset_repository.delete(dataset_id)
        return DatasetDeleteResponse(id=dataset_id, deleted=True)

    def _build_summary(self, dataset: DatasetOrm) -> DatasetSummary:
        linked_sessions = self._linked_sessions(dataset.id)
        linked_session_ids = [session_id for session_id, _ in linked_sessions]
        latest_used_at = linked_sessions[0][1] if linked_sessions else None
        row_count, column_count = self._get_dataset_shape(dataset)
        return DatasetSummary(
            **self._to_dataset_info(dataset).model_dump(),
            row_count=row_count,
            column_count=column_count,
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

    def _load_dataframe_from_dataset(self, dataset: DatasetOrm) -> pd.DataFrame:
        return self._infer_datetime_columns(load_dataframe(Path(dataset.storage_path)))

    def _get_stored_preview(self, dataset: DatasetOrm) -> DatasetPreviewPayload | None:
        """DB에 저장된 미리보기 payload를 DTO로 복원합니다."""
        if dataset.preview is None:
            return None
        return DatasetPreviewPayload.model_validate(dataset.preview)

    def _get_stored_profile(self, dataset: DatasetOrm) -> DatasetProfilePayload | None:
        """DB에 저장된 프로파일 payload를 DTO로 복원합니다."""
        if dataset.profile is None:
            return None
        return DatasetProfilePayload.model_validate(dataset.profile)

    def _get_dataset_shape(self, dataset: DatasetOrm) -> tuple[int, int]:
        """저장된 프로파일에서 데이터셋 크기를 조회하고 없으면 파일에서 계산합니다."""
        profile = self._get_stored_profile(dataset)
        if profile is not None:
            return profile.row_count, profile.column_count

        dataframe = self._load_dataframe_from_dataset(dataset)
        return len(dataframe.index), len(dataframe.columns)

    def _to_dataset_info(self, dataset: DatasetOrm) -> DatasetInfo:
        return DatasetInfo(
            id=dataset.id,
            filename=dataset.filename,
            storage_path=dataset.storage_path,
            created_at=dataset.created_at,
        )
