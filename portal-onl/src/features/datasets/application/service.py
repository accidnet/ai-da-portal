import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi import UploadFile

from core.paths import UPLOADED_DATASET_DIR
from domain.sessions.service import SessionService
from features.data_sources.domain.models import DataSourceItem
from features.data_sources.infrastructure.repositories import DataSourceRepository
from features.datasets.api.schemas import (
    CreateDatasetFromSourcesRequest,
    DatasetDeleteResponse,
    DatasetInfo,
    DatasetPreviewResponse,
    DatasetProfileResponse,
    DatasetSourcesResponse,
    DatasetSourceTreeNode,
    DatasetSummary,
)
from features.datasets.application.dataframe_loader import load_dataframe
from features.datasets.application.dto import (
    DatasetColumnProfile,
    DatasetPreviewPayload,
    DatasetProfilePayload,
)
from features.datasets.application.inspection import (
    build_preview_from_dataframe,
    build_profile_from_dataframe,
)
from features.datasets.application.profiling import (
    build_profile_snapshot_from_path,
    infer_datetime_columns,
)
from infrastructure.db.repositories import DatasetRecord, DatasetRepository


logger = logging.getLogger(__name__)


class DatasetApplicationService:
    """업로드된 원천 데이터의 저장, 조회, 프로파일 생성을 담당합니다."""

    def __init__(
        self,
        dataset_repository: DatasetRepository,
        session_service: SessionService | None = None,
        data_source_repository: DataSourceRepository | None = None,
    ) -> None:
        self._dataset_repository = dataset_repository
        self._session_service = session_service
        self._data_source_repository = data_source_repository

    async def upload(self, file: UploadFile) -> DatasetInfo:
        """원천 데이터 파일을 저장하고, 가능한 경우 표 형태 프로파일을 생성합니다."""
        # dataset 고유 id 부여
        dataset_id = str(uuid4())

        # filename 추출
        filename = file.filename or "dataset.csv"

        # 업로드 파일은 청크로 저장해 대용량 파일이 메모리에 한 번에 올라오지 않게 합니다.
        storage_path = await self._store_uploaded_file(dataset_id, filename, file)

        # 표 형태로 읽을 수 없는 파일도 원천 데이터로 보관하기 위해 빈 프로파일을 사용합니다.
        logger.debug(
            "Building dataset source profile snapshot 1/1: dataset_id=%s filename=%s path=%s",
            dataset_id,
            filename,
            storage_path,
        )
        try:
            preview, profile = build_profile_snapshot_from_path(storage_path)
            logger.debug(
                "Built dataset source profile snapshot 1/1: dataset_id=%s filename=%s rows=%s columns=%s",
                dataset_id,
                filename,
                profile.row_count,
                profile.column_count,
            )
        except Exception as exc:
            logger.debug(
                "Failed to build dataset source profile snapshot 1/1: dataset_id=%s filename=%s error=%s",
                dataset_id,
                filename,
                exc,
                exc_info=True,
            )
            preview = DatasetPreviewPayload()
            profile = DatasetProfilePayload(row_count=0, column_count=0)

        source_id = str(uuid4())
        # Dataset 기본 정보
        dataset = self._dataset_repository.create(
            dataset_id=dataset_id,
            created_at=datetime.now(UTC),
            name=filename,
            sources=[
                {
                    "id": source_id,
                    "source_ref_id": None,
                }
            ],
            source_profiles=[
                {
                    "dataset_source_id": source_id,
                    "row_count": profile.row_count,
                    "column_count": profile.column_count,
                    "preview": preview.model_dump(mode="json"),
                    "profile": profile.model_dump(mode="json"),
                }
            ],
        )
        return self._to_dataset_info(dataset)

    def create_from_sources(
        self, request: CreateDatasetFromSourcesRequest
    ) -> DatasetInfo:
        """원천 데이터 또는 향후 DB 선택 정보를 기반으로 데이터셋을 생성합니다."""
        name = request.name.strip()
        if not name:
            raise ValueError("Dataset name is required.")

        if self._data_source_repository is None:
            raise RuntimeError("Data source repository is not configured.")

        selected_items = self._data_source_repository.list_items_by_ids(
            request.data_source_item_ids
        )
        selected_files = self._expand_selected_source_files(selected_items)
        if not selected_files:
            raise ValueError("At least one source file is required.")

        dataset_id = str(uuid4())
        source_id_by_item_id = {item.id: str(uuid4()) for item in selected_files}
        source_profiles = self._build_source_profiles(
            selected_files,
            source_id_by_item_id,
        )

        dataset = self._dataset_repository.create(
            dataset_id=dataset_id,
            created_at=datetime.now(UTC),
            name=name,
            description=request.description.strip() if request.description else None,
            sources=[
                {
                    "id": source_id_by_item_id[item.id],
                    "source_ref_id": item.id,
                }
                for item in selected_files
            ],
            source_profiles=source_profiles,
        )
        return self._to_dataset_info(dataset)

    def list_datasets(self) -> list[DatasetSummary]:
        """등록된 데이터셋 목록을 최신순 요약으로 반환합니다."""
        return [
            self._build_summary(dataset)
            for dataset in self._dataset_repository.list_datasets()
        ]

    def get(self, dataset_id: str) -> DatasetInfo:
        """데이터셋 ID로 기본 정보를 조회합니다."""
        return self._to_dataset_info(self._dataset_repository.get_or_raise(dataset_id))

    def get_profile(self, dataset_id: str) -> DatasetProfileResponse:
        """데이터셋 ID로 프로파일 스냅샷 또는 원천 파일 기반 프로파일을 반환합니다."""
        dataset = self._dataset_repository.get_or_raise(dataset_id)
        return DatasetProfileResponse(
            dataset_id=dataset_id,
            profile=self._build_profile_from_dataset_sources(dataset),
        )

    def get_preview(self, dataset_id: str) -> DatasetPreviewResponse:
        """데이터셋 ID로 미리보기 스냅샷 또는 원천 파일 기반 미리보기를 반환합니다."""
        dataset = self._dataset_repository.get_or_raise(dataset_id)
        preview = self._build_preview_from_dataset_sources(dataset)
        return DatasetPreviewResponse(
            dataset_id=dataset_id,
            columns=preview.columns,
            rows=preview.rows,
        )

    def get_sources(self, dataset_id: str) -> DatasetSourcesResponse:
        """데이터셋에 연결된 원천 파일 목록을 폴더 트리 형태로 반환합니다."""
        dataset = self._dataset_repository.get_or_raise(dataset_id)
        return DatasetSourcesResponse(
            dataset_id=dataset_id,
            sources=self._build_dataset_source_tree(dataset),
        )

    def get_dataframe(self, dataset_id: str) -> pd.DataFrame:
        """데이터셋 원천 파일들을 하나의 DataFrame으로 로드합니다."""
        dataset = self._dataset_repository.get_or_raise(dataset_id)
        return self._load_dataframe_from_dataset(dataset)

    def get_latest_dataset_id(self) -> str | None:
        """가장 최근 등록된 데이터셋 ID를 반환합니다."""
        dataset = self._dataset_repository.get_latest()
        return dataset.id if dataset is not None else None

    def get_uploaded_filenames(self, dataset_ids: list[str]) -> list[str]:
        """지정한 데이터셋 ID들의 표시 파일명을 중복 없이 반환합니다."""
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
        """레거시 파일명 기반 도구 호출을 위해 최신 업로드 파일을 로드합니다."""
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
        """세션에 연결되지 않은 데이터셋을 삭제합니다."""
        linked_sessions = self._linked_sessions(dataset_id)
        if linked_sessions:
            raise ValueError("Dataset is still linked to one or more sessions.")
        self._dataset_repository.delete(dataset_id)
        return DatasetDeleteResponse(id=dataset_id, deleted=True)

    def _build_summary(self, dataset: DatasetRecord) -> DatasetSummary:
        """데이터셋 record와 세션 연결 정보를 목록 요약으로 변환합니다."""
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
        """세션 서비스가 있으면 데이터셋 연결 세션 목록을 조회합니다."""
        if self._session_service is None:
            return []
        return self._session_service.list_linked_sessions(dataset_id)

    async def _store_uploaded_file(
        self, dataset_id: str, filename: str, file: UploadFile
    ) -> Path:
        """업로드 파일을 메모리 적재 없이 디스크에 청크 단위로 저장합니다."""
        UPLOADED_DATASET_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name or "dataset.csv"
        stored_path = UPLOADED_DATASET_DIR / f"{dataset_id}__{safe_name}"
        with stored_path.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                target.write(chunk)
        return stored_path

    def _expand_selected_source_files(
        self, selected_items: list[DataSourceItem]
    ) -> list[DataSourceItem]:
        """폴더 선택을 하위 파일 전체 선택으로 확장하고 중복 파일을 제거합니다."""
        if self._data_source_repository is None:
            return []

        file_map: dict[str, DataSourceItem] = {}
        for item in selected_items:
            if item.item_type == "file" and item.storage_path:
                file_map[item.id] = item
                continue

            if item.item_type == "folder":
                for descendant in self._data_source_repository.list_descendants(
                    item.relative_path
                ):
                    if descendant.item_type == "file" and descendant.storage_path:
                        file_map[descendant.id] = descendant

        return sorted(file_map.values(), key=lambda item: item.relative_path)

    def _infer_datetime_columns(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """DataFrame의 날짜형 문자열 컬럼을 공통 추론 로직으로 변환합니다."""
        return infer_datetime_columns(dataframe)

    def _load_dataframe_from_dataset(self, dataset: DatasetRecord) -> pd.DataFrame:
        """데이터셋 원천 파일 목록을 병합해 단일 DataFrame을 구성합니다."""
        dataframes = self._load_source_dataframes(dataset)
        if not dataframes:
            raise ValueError("Dataset has no readable source files.")
        frames = []
        for source_path, dataframe in dataframes:
            frame = dataframe.copy()
            if len(dataframes) > 1:
                frame["__source_path"] = source_path
            frames.append(frame)
        return pd.concat(frames, ignore_index=True, sort=False)

    def _get_dataset_shape(self, dataset: DatasetRecord) -> tuple[int, int]:
        """원천 데이터 파일 기준으로 데이터셋 크기를 계산합니다."""
        profile = self._build_profile_from_dataset_sources(dataset)
        return profile.row_count, profile.column_count

    def _to_dataset_info(self, dataset: DatasetRecord) -> DatasetInfo:
        """저장소 record를 API 기본 정보 응답으로 변환합니다."""
        return DatasetInfo(
            id=dataset.id,
            filename=dataset.filename,
            name=dataset.name or dataset.filename,
            description=dataset.description,
            storage_path=dataset.storage_path,
            created_at=dataset.created_at,
        )

    def _load_source_dataframes(
        self, dataset: DatasetRecord
    ) -> list[tuple[str, pd.DataFrame]]:
        """데이터셋 원천 연결을 data_source_items 기준으로 로드합니다."""
        frames: list[tuple[str, pd.DataFrame]] = []
        source_ref_ids = [
            source.source_ref_id
            for source in dataset.sources
            if source.source_ref_id is not None
        ]
        if source_ref_ids and self._data_source_repository is not None:
            source_items = self._data_source_repository.list_items_by_ids(
                source_ref_ids
            )
            for item in source_items:
                if item.storage_path is None:
                    continue
                try:
                    dataframe = self._infer_datetime_columns(
                        load_dataframe(Path(item.storage_path))
                    )
                except Exception:
                    continue
                frames.append((item.relative_path, dataframe))
            return frames

        if dataset.storage_path:
            dataframe = self._load_dataframe_from_dataset_path(dataset.storage_path)
            frames.append((dataset.filename, dataframe))
        return frames

    def _build_source_profiles(
        self,
        selected_files: list[DataSourceItem],
        source_id_by_item_id: dict[str, str],
    ) -> list[dict[str, object]]:
        """데이터셋 등록 시점에 원천 파일별 preview/profile 스냅샷을 생성합니다."""
        source_profiles: list[dict[str, object]] = []
        total_count = len(selected_files)
        logger.debug(
            "Building dataset source profile snapshots: total=%s",
            total_count,
        )
        for index, item in enumerate(selected_files, start=1):
            if item.storage_path is None:
                logger.debug(
                    "Skipping dataset source profile snapshot %s/%s: source_id=%s path missing",
                    index,
                    total_count,
                    item.id,
                )
                continue
            logger.debug(
                "Building dataset source profile snapshot %s/%s: source_id=%s name=%s relative_path=%s path=%s",
                index,
                total_count,
                item.id,
                item.name,
                item.relative_path,
                item.storage_path,
            )
            try:
                preview, profile = build_profile_snapshot_from_path(
                    Path(item.storage_path)
                )
                logger.debug(
                    "Built dataset source profile snapshot %s/%s: source_id=%s rows=%s columns=%s",
                    index,
                    total_count,
                    item.id,
                    profile.row_count,
                    profile.column_count,
                )
            except Exception as exc:
                logger.debug(
                    "Failed to build dataset source profile snapshot %s/%s: source_id=%s error=%s",
                    index,
                    total_count,
                    item.id,
                    exc,
                    exc_info=True,
                )
                preview = DatasetPreviewPayload()
                profile = DatasetProfilePayload(row_count=0, column_count=0)

            source_profiles.append(
                {
                    "dataset_source_id": source_id_by_item_id[item.id],
                    "row_count": profile.row_count,
                    "column_count": profile.column_count,
                    "preview": preview.model_dump(mode="json"),
                    "profile": profile.model_dump(mode="json"),
                }
            )
        return source_profiles

    def _load_dataframe_from_dataset_path(self, storage_path: str) -> pd.DataFrame:
        """저장 경로를 기준으로 DataFrame을 로드합니다."""
        return self._infer_datetime_columns(load_dataframe(Path(storage_path)))

    def _build_preview_from_dataset_sources(
        self, dataset: DatasetRecord
    ) -> DatasetPreviewPayload:
        """원천 데이터 파일 preview를 합쳐 데이터셋 미리보기를 만듭니다."""
        stored_preview = self._build_preview_from_stored_source_profiles(dataset)
        if stored_preview is not None:
            return stored_preview

        dataframes = self._load_source_dataframes(dataset)
        columns: list[str] = []
        rows: list[dict[str, str | int | float | None]] = []
        seen_columns: set[str] = set()

        for source_path, dataframe in dataframes:
            preview = build_preview_from_dataframe(dataframe)
            for column in preview.columns:
                if column not in seen_columns:
                    seen_columns.add(column)
                    columns.append(column)
            for row in preview.rows[:5]:
                rows.append({"__source_path": source_path, **row})
            if len(rows) >= 20:
                break

        if rows:
            columns = ["__source_path", *columns]
        return DatasetPreviewPayload(columns=columns, rows=rows[:20])

    def _build_profile_from_dataset_sources(
        self, dataset: DatasetRecord
    ) -> DatasetProfilePayload:
        """원천 데이터 파일 profile을 행 수 합산과 컬럼 union 기준으로 만듭니다."""
        stored_profile = self._build_profile_from_stored_source_profiles(dataset)
        if stored_profile is not None:
            return stored_profile

        dataframes = self._load_source_dataframes(dataset)
        row_count = 0
        columns: dict[str, DatasetColumnProfile] = {}
        for _, dataframe in dataframes:
            profile = build_profile_from_dataframe(dataframe)
            row_count += profile.row_count
            for column in profile.columns:
                columns.setdefault(column.name, column)

        return DatasetProfilePayload(
            row_count=row_count,
            column_count=len(columns),
            columns=list(columns.values()),
        )

    def _build_preview_from_stored_source_profiles(
        self, dataset: DatasetRecord
    ) -> DatasetPreviewPayload | None:
        """저장된 원천 파일별 preview 스냅샷으로 데이터셋 미리보기를 만듭니다."""
        columns: list[str] = []
        rows: list[dict[str, str | int | float | None]] = []
        seen_columns: set[str] = set()
        has_snapshot = False

        for source in dataset.sources:
            if source.preview is None:
                continue
            has_snapshot = True
            preview = DatasetPreviewPayload.model_validate(source.preview)
            for column in preview.columns:
                if column not in seen_columns:
                    seen_columns.add(column)
                    columns.append(column)
            for row in preview.rows[:5]:
                rows.append(row)
            if len(rows) >= 20:
                break

        if not has_snapshot:
            return None
        return DatasetPreviewPayload(columns=columns, rows=rows[:20])

    def _build_profile_from_stored_source_profiles(
        self, dataset: DatasetRecord
    ) -> DatasetProfilePayload | None:
        """저장된 원천 파일별 profile 스냅샷으로 데이터셋 프로파일을 만듭니다."""
        row_count = 0
        columns: dict[str, DatasetColumnProfile] = {}
        has_snapshot = False
        for source in dataset.sources:
            if source.profile is None:
                continue
            has_snapshot = True
            profile = DatasetProfilePayload.model_validate(source.profile)
            row_count += profile.row_count
            for column in profile.columns:
                columns.setdefault(column.name, column)

        if not has_snapshot:
            return None
        return DatasetProfilePayload(
            row_count=row_count,
            column_count=len(columns),
            columns=list(columns.values()),
        )

    def _build_dataset_source_tree(
        self, dataset: DatasetRecord
    ) -> list[DatasetSourceTreeNode]:
        """파일 단위 source 연결을 원천 데이터 경로 기준 트리로 복원합니다."""
        if self._data_source_repository is None:
            return []

        source_by_ref_id = {
            source.source_ref_id: source
            for source in dataset.sources
            if source.source_ref_id is not None
        }
        source_ref_ids = list(source_by_ref_id.keys())
        source_items = self._data_source_repository.list_items_by_ids(source_ref_ids)

        root_nodes: dict[str, dict[str, object]] = {}
        node_by_path: dict[str, dict[str, object]] = {}

        for item in sorted(source_items, key=lambda value: value.relative_path):
            path_parts = [part for part in item.relative_path.split("/") if part]
            if not path_parts:
                continue

            parent_children = root_nodes
            current_path_parts: list[str] = []
            for index, part in enumerate(path_parts):
                current_path_parts.append(part)
                current_path = "/".join(current_path_parts)
                is_file = index == len(path_parts) - 1
                source = source_by_ref_id.get(item.id) if is_file else None

                if current_path not in node_by_path:
                    node_by_path[current_path] = {
                        "id": item.id if is_file else f"folder:{current_path}",
                        "source_ref_id": item.id if is_file else None,
                        "item_type": "file" if is_file else "folder",
                        "name": item.name if is_file else part,
                        "relative_path": current_path,
                        "depth": index,
                        "content_type": item.content_type if is_file else None,
                        "size_bytes": item.size_bytes if is_file else None,
                        "row_count": source.row_count if source is not None else 0,
                        "column_count": source.column_count
                        if source is not None
                        else 0,
                        "file_count": 1 if is_file else 0,
                        "children": {},
                    }
                    parent_children[current_path] = node_by_path[current_path]

                node = node_by_path[current_path]
                if is_file:
                    break
                parent_children = node["children"]  # type: ignore[assignment]

        def finalize_node(node: dict[str, object]) -> DatasetSourceTreeNode:
            children_map = node["children"]
            children = [
                finalize_node(child)
                for child in sorted(
                    children_map.values(),  # type: ignore[union-attr]
                    key=lambda child: (
                        0 if child["item_type"] == "folder" else 1,
                        str(child["name"]).lower(),
                    ),
                )
            ]
            if node["item_type"] == "folder":
                node["row_count"] = sum(child.row_count for child in children)
                node["file_count"] = sum(child.file_count for child in children)
                node["column_count"] = max(
                    [child.column_count for child in children],
                    default=0,
                )

            return DatasetSourceTreeNode(
                id=str(node["id"]),
                source_ref_id=(
                    str(node["source_ref_id"])
                    if node["source_ref_id"] is not None
                    else None
                ),
                item_type=str(node["item_type"]),
                name=str(node["name"]),
                relative_path=str(node["relative_path"]),
                depth=int(node["depth"]),
                content_type=(
                    str(node["content_type"])
                    if node["content_type"] is not None
                    else None
                ),
                size_bytes=(
                    int(node["size_bytes"]) if node["size_bytes"] is not None else None
                ),
                row_count=int(node["row_count"]),
                column_count=int(node["column_count"]),
                file_count=int(node["file_count"]),
                children=children,
            )

        return [
            finalize_node(node)
            for node in sorted(
                root_nodes.values(),
                key=lambda child: (
                    0 if child["item_type"] == "folder" else 1,
                    str(child["name"]).lower(),
                ),
            )
        ]
