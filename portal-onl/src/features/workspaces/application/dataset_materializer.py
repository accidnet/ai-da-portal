import logging
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from features.data_sources.infrastructure.repositories import DataSourceRepository
from features.datasets.application.source_loading import resolve_dataset_source_paths
from infrastructure.db.repositories import DatasetRepository

logger = logging.getLogger(__name__)
DATASET_WORKSPACE_DIR = "datasets"


@dataclass(frozen=True, slots=True)
class WorkspaceDatasetFile:
    """LLM과 CLI에 노출할 워크스페이스 내부 dataset 파일 경로입니다."""

    dataset_id: str
    source_path: str
    workspace_path: str
    size_bytes: int


class WorkspaceDatasetMaterializer:
    """dataset 원본 파일을 워크스페이스 내부 상대 경로로 노출합니다."""

    def __init__(
        self,
        *,
        dataset_repository: DatasetRepository,
        data_source_repository: DataSourceRepository,
    ) -> None:
        self._dataset_repository = dataset_repository
        self._data_source_repository = data_source_repository

    def materialize(
        self,
        *,
        workspace_root: Path,
        dataset_ids: list[str],
    ) -> list[WorkspaceDatasetFile]:
        """연결 dataset 파일을 워크스페이스 내부 datasets 디렉터리에 복사합니다."""
        workspace_root = workspace_root.resolve()
        unique_dataset_ids = list(dict.fromkeys(dataset_ids))
        self._cleanup_unlinked_dataset_dirs(workspace_root, unique_dataset_ids)
        dataset_files: list[WorkspaceDatasetFile] = []
        for dataset_id in unique_dataset_ids:
            try:
                dataset = self._dataset_repository.get_or_raise(dataset_id)
            except KeyError:
                logger.warning(
                    "Skipping workspace dataset materialization for missing dataset_id=%s",
                    dataset_id,
                )
                continue

            dataset_dir = workspace_root / DATASET_WORKSPACE_DIR / dataset_id
            dataset_dir.mkdir(parents=True, exist_ok=True)
            used_paths: set[str] = set()
            for source_path, actual_path in resolve_dataset_source_paths(
                dataset,
                self._data_source_repository,
            ):
                if not actual_path.is_file():
                    logger.warning(
                        "Skipping missing dataset source file dataset_id=%s source_path=%s actual_path=%s",
                        dataset_id,
                        source_path,
                        actual_path,
                    )
                    continue

                relative_source_path = self._dedupe_relative_path(
                    self._safe_relative_path(source_path),
                    used_paths,
                )
                target_path = dataset_dir / relative_source_path
                self._copy_source_file(actual_path, target_path)
                dataset_files.append(
                    WorkspaceDatasetFile(
                        dataset_id=dataset_id,
                        source_path=source_path,
                        workspace_path=target_path.relative_to(
                            workspace_root
                        ).as_posix(),
                        size_bytes=target_path.stat().st_size,
                    )
                )

        return dataset_files

    def _cleanup_unlinked_dataset_dirs(
        self,
        workspace_root: Path,
        dataset_ids: list[str],
    ) -> None:
        """현재 컨텍스트와 무관한 이전 dataset 디렉터리는 LLM 목록에서 숨깁니다."""
        datasets_root = workspace_root / DATASET_WORKSPACE_DIR
        if not datasets_root.is_dir():
            return
        allowed_dataset_ids = set(dataset_ids)
        for child in datasets_root.iterdir():
            if child.name in allowed_dataset_ids:
                continue
            if child.is_symlink():
                child.unlink(missing_ok=True)
                continue
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            elif child.is_file():
                child.unlink(missing_ok=True)

    def _copy_source_file(self, source_path: Path, target_path: Path) -> None:
        """절대 원본 경로가 노출되지 않도록 워크스페이스 내부 파일로 복사합니다."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if self._is_current_copy(source_path, target_path):
            return
        shutil.copy2(source_path, target_path)

    def _is_current_copy(self, source_path: Path, target_path: Path) -> bool:
        """이미 복사된 파일이 원본과 같은 크기/수정시각이면 재복사를 피합니다."""
        if not target_path.is_file():
            return False
        source_stat = source_path.stat()
        target_stat = target_path.stat()
        return (
            source_stat.st_size == target_stat.st_size
            and int(source_stat.st_mtime) == int(target_stat.st_mtime)
        )

    def _safe_relative_path(self, value: str) -> Path:
        """원천 파일 표시 경로를 workspace 내부에서만 쓰는 안전한 상대 경로로 정규화합니다."""
        parts = [
            Path(part).name
            for part in PurePosixPath(value).parts
            if part not in {"", ".", "..", "/"}
        ]
        if not parts:
            return Path("dataset")
        return Path(*parts)

    def _dedupe_relative_path(self, relative_path: Path, used_paths: set[str]) -> Path:
        """같은 dataset 안에서 같은 파일명이 겹치면 suffix로 충돌을 해소합니다."""
        candidate = relative_path
        suffix = 1
        while candidate.as_posix() in used_paths:
            stem = relative_path.stem or "dataset"
            candidate = relative_path.with_name(
                f"{stem}_{suffix}{relative_path.suffix}"
            )
            suffix += 1
        used_paths.add(candidate.as_posix())
        return candidate
