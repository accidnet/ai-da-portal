from pathlib import PurePosixPath
from pathlib import Path
from uuid import uuid4

from core.paths import DATA_SOURCE_STORAGE_DIR
from features.data_sources.application.dto import (
    DataSourceItemResult,
    DataSourceDeleteResult,
    DataSourceUploadCommand,
    DataSourceUploadResult,
)
from features.data_sources.domain.models import DataSourceItem
from features.data_sources.infrastructure.repositories import DataSourceRepository


class DataSourceUsecase:
    """원천 데이터 직접 업로드와 트리 조회 유스케이스를 수행합니다."""

    def __init__(self, repository: DataSourceRepository) -> None:
        self._repository = repository

    def upload(self, command: DataSourceUploadCommand) -> DataSourceUploadResult:
        """파일/폴더 선택 결과를 flat 저장하고 DB 노드로 트리를 재현합니다."""
        if not command.files:
            raise ValueError("At least one file is required.")

        normalized_paths = self._normalize_upload_paths(
            command,
            existing_paths=self._repository.list_relative_paths(),
        )
        items = self._build_item_rows(command, normalized_paths)
        saved_items = self._repository.create_items(items=items)
        return DataSourceUploadResult(
            items=[self._to_item_result(item) for item in saved_items],
        )

    def list_items(self) -> list[DataSourceItemResult]:
        """저장된 원천 데이터 파일/폴더 노드를 조회합니다."""
        return [self._to_item_result(item) for item in self._repository.list_items()]

    def delete(self, item_id: str) -> DataSourceDeleteResult:
        """원천 데이터 파일/폴더 노드와 실제 저장 파일을 삭제합니다."""
        storage_paths = self._repository.delete_item_tree(item_id)
        for storage_path in storage_paths:
            try:
                Path(storage_path).unlink(missing_ok=True)
            except OSError:
                continue
        return DataSourceDeleteResult(
            id=item_id,
            deleted=True,
            deleted_count=len(storage_paths),
        )

    def _build_item_rows(
        self,
        command: DataSourceUploadCommand,
        normalized_paths: list[str],
    ) -> list[dict[str, object]]:
        """업로드 파일 경로에서 folder/file 노드를 생성합니다."""
        DATA_SOURCE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        items: list[dict[str, object]] = []
        path_to_id: dict[str, str] = {}

        for index, (file, relative_path) in enumerate(
            zip(command.files, normalized_paths, strict=True)
        ):
            parts = relative_path.split("/")
            parent_id: str | None = None
            ancestor_parts: list[str] = []

            for depth, folder_name in enumerate(parts[:-1]):
                ancestor_parts.append(folder_name)
                folder_path = "/".join(ancestor_parts)
                if folder_path in path_to_id:
                    parent_id = path_to_id[folder_path]
                    continue

                folder_id = str(uuid4())
                path_to_id[folder_path] = folder_id
                items.append(
                    {
                        "id": folder_id,
                        "parent_id": parent_id,
                        "item_type": "folder",
                        "name": folder_name,
                        "relative_path": folder_path,
                        "depth": depth,
                        "sort_order": len(items),
                        "content_type": None,
                        "size_bytes": None,
                        "storage_path": None,
                    }
                )
                parent_id = folder_id

            file_id = str(uuid4())
            storage_path = self._store_flat_file(
                item_id=file_id,
                filename=parts[-1],
                content=file.content,
            )
            items.append(
                {
                    "id": file_id,
                    "parent_id": parent_id,
                    "item_type": "file",
                    "name": parts[-1],
                    "relative_path": relative_path,
                    "depth": len(parts) - 1,
                    "sort_order": index,
                    "content_type": file.content_type,
                    "size_bytes": len(file.content),
                    "storage_path": str(storage_path),
                }
            )

        return items

    def _store_flat_file(self, *, item_id: str, filename: str, content: bytes):
        """트리 경로와 무관하게 item id 기반의 단일 디렉토리에 파일을 저장합니다."""
        safe_name = PurePosixPath(filename).name or "uploaded-file"
        stored_path = DATA_SOURCE_STORAGE_DIR / f"{item_id}__{safe_name}"
        stored_path.write_bytes(content)
        return stored_path

    def _normalize_upload_paths(
        self,
        command: DataSourceUploadCommand,
        *,
        existing_paths: set[str],
    ) -> list[str]:
        """브라우저가 전달한 파일/폴더 경로를 안전한 POSIX 상대 경로로 정리합니다."""
        paths: list[str] = []
        for index, file in enumerate(command.files):
            raw_path = (
                command.relative_paths[index]
                if index < len(command.relative_paths) and command.relative_paths[index]
                else file.filename
            )
            paths.append(self._normalize_relative_path(raw_path))
        return self._dedupe_paths(paths, existing_paths=existing_paths)

    def _normalize_relative_path(self, value: str) -> str:
        """절대 경로와 상위 디렉토리 참조를 제거한 상대 경로를 반환합니다."""
        parts = [
            part.strip()
            for part in PurePosixPath(value.replace("\\", "/")).parts
            if part.strip() and part not in {".", "..", "/"}
        ]
        if not parts:
            return "uploaded-file"
        return "/".join(parts)

    def _dedupe_paths(self, paths: list[str], *, existing_paths: set[str]) -> list[str]:
        """기존 DB 경로와 이번 업로드 경로를 모두 고려해 유일한 경로를 만듭니다."""
        reserved = set(existing_paths)
        deduped: list[str] = []
        for path in paths:
            unique_path = self._next_available_path(path, reserved)
            reserved.add(unique_path)
            deduped.append(unique_path)
        return deduped

    def _next_available_path(self, path: str, reserved: set[str]) -> str:
        """상대 경로가 이미 있으면 파일명에 번호를 붙여 다음 경로를 반환합니다."""
        if path not in reserved:
            return path

        target = PurePosixPath(path)
        stem = target.stem or target.name
        suffix = target.suffix
        parent = str(target.parent)
        index = 2

        while True:
            name = f"{stem} ({index}){suffix}"
            candidate = name if parent == "." else f"{parent}/{name}"
            if candidate not in reserved:
                return candidate
            index += 1

    def _to_item_result(self, item: DataSourceItem) -> DataSourceItemResult:
        """domain 파일/폴더 노드를 application 출력 DTO로 변환합니다."""
        return DataSourceItemResult(
            id=item.id,
            parent_id=item.parent_id,
            item_type=item.item_type,
            name=item.name,
            relative_path=item.relative_path,
            depth=item.depth,
            sort_order=item.sort_order,
            content_type=item.content_type,
            size_bytes=item.size_bytes,
            storage_path=item.storage_path,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
