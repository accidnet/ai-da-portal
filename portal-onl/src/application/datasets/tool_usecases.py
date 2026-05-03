from pathlib import Path

import pandas as pd

from application.datasets.dto import (
    DatasetPreviewPayload,
    DatasetProfilePayload,
)
from application.datasets.inspection import (
    build_preview_from_dataframe,
    build_profile_from_dataframe,
)
from application.datasets.ports import DatasetMetadataReader, DatasetMetadataRecord
from tools.dto import (
    DatasetInspectionPayload,
    DatasetToolPreviewPayload,
    DatasetToolProfilePayload,
)
from tools.datasets.dataframe_loader import load_dataframe


class InspectDatasetContextUseCase:
    """데이터셋 tool 호출에 필요한 미리보기와 프로파일을 제공합니다."""

    def __init__(self, dataset_reader: DatasetMetadataReader) -> None:
        # usecase는 저장소 구현체 대신 application port에만 의존합니다.
        self._dataset_reader = dataset_reader

    def execute(self, dataset_id: str) -> DatasetInspectionPayload:
        """특정 데이터셋 ID의 프로파일과 미리보기를 tool 응답 payload로 반환합니다."""
        dataset = self._dataset_reader.get_or_raise(dataset_id)
        profile = self._get_stored_profile(dataset)
        preview = self._get_stored_preview(dataset)
        if profile is None or preview is None:
            dataframe = self._load_dataframe_from_dataset(dataset)
            profile = profile or build_profile_from_dataframe(dataframe)
            preview = preview or build_preview_from_dataframe(dataframe)

        return DatasetInspectionPayload(
            dataset_id=dataset_id,
            profile=DatasetToolProfilePayload(dataset_id=dataset_id, profile=profile),
            preview=DatasetToolPreviewPayload(
                dataset_id=dataset_id,
                columns=preview.columns,
                rows=preview.rows,
            ),
        )

    def execute_many(self, dataset_ids: list[str]) -> list[DatasetInspectionPayload]:
        """여러 데이터셋 ID의 프로파일과 미리보기를 순서대로 반환합니다."""
        # LLM이 요청한 dataset_id 순서를 유지해 비교 질문에서 참조하기 쉽게 합니다.
        return [self.execute(dataset_id) for dataset_id in dataset_ids]

    def _load_dataframe_from_dataset(
        self, dataset: DatasetMetadataRecord
    ) -> pd.DataFrame:
        """저장 경로의 원본 파일을 DataFrame으로 로드하고 날짜 컬럼을 보정합니다."""
        return self._infer_datetime_columns(load_dataframe(Path(dataset.storage_path)))

    def _infer_datetime_columns(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """object 컬럼 중 날짜로 해석 가능한 컬럼을 datetime 타입으로 변환합니다."""
        inferred = dataframe.copy()
        for column in inferred.columns:
            series = inferred[column]
            if not pd.api.types.is_object_dtype(series):
                continue
            converted = pd.to_datetime(series, errors="coerce", format="mixed")
            if converted.notna().mean() >= 0.8 and converted.notna().any():
                inferred[column] = converted
        return inferred

    def _get_stored_preview(
        self, dataset: DatasetMetadataRecord
    ) -> DatasetPreviewPayload | None:
        """DB에 저장된 미리보기 payload를 DTO로 복원합니다."""
        if dataset.preview is None:
            return None
        return DatasetPreviewPayload.model_validate(dataset.preview)

    def _get_stored_profile(
        self, dataset: DatasetMetadataRecord
    ) -> DatasetProfilePayload | None:
        """DB에 저장된 프로파일 payload를 DTO로 복원합니다."""
        if dataset.profile is None:
            return None
        return DatasetProfilePayload.model_validate(dataset.profile)
