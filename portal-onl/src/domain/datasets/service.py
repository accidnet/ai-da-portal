from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from core.config import get_settings
from domain.datasets.preview import build_placeholder_preview
from domain.datasets.profiling import build_placeholder_profile
from domain.datasets.schemas import (
    DatasetDetail,
    DatasetPreviewResponse,
    DatasetProfileResponse,
)
from infrastructure.storage.files import save_upload_file


class DatasetService:
    async def upload(self, file: UploadFile) -> DatasetDetail:
        settings = get_settings()
        dataset_id = str(uuid4())
        suffix = Path(file.filename or "dataset.csv").suffix
        storage_path = f"{settings.uploads_dir}/{dataset_id}{suffix}"
        await save_upload_file(file=file, destination=Path(storage_path))

        return DatasetDetail(
            id=dataset_id,
            filename=file.filename or "dataset.csv",
            content_type=file.content_type,
            storage_path=storage_path,
            created_at=datetime.now(UTC),
        )

    def get(self, dataset_id: str) -> DatasetDetail:
        return DatasetDetail(
            id=dataset_id,
            filename="sample-dataset.csv",
            content_type="text/csv",
            storage_path=f"storage/uploads/{dataset_id}.csv",
            created_at=datetime.now(UTC),
        )

    def get_profile(self, dataset_id: str) -> DatasetProfileResponse:
        return DatasetProfileResponse(
            dataset_id=dataset_id, profile=build_placeholder_profile()
        )

    def get_preview(self, dataset_id: str) -> DatasetPreviewResponse:
        columns, rows = build_placeholder_preview()
        return DatasetPreviewResponse(dataset_id=dataset_id, columns=columns, rows=rows)
