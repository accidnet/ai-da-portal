from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from features.workspaces.application.dto import (
    WorkspaceCreateCommand,
    WorkspaceDatasetLinkResult,
    WorkspaceDeleteResult,
    WorkspaceFileContentResult,
    WorkspaceFileEntryResult,
    WorkspaceFileListResult,
    WorkspaceResult,
    WorkspaceUpdateCommand,
)
from features.workspaces.application.local_storage import WorkspaceLocalStorage
from features.workspaces.domain.models import Workspace
from features.workspaces.domain.repositories import WorkspaceRepository


class WorkspaceUsecase:
    """워크스페이스 생성과 조회 유스케이스를 수행합니다."""

    _DEFAULT_MAX_ENTRIES = 200
    _MAX_ENTRIES = 500
    _DEFAULT_MAX_READ_BYTES = 512_000
    _MAX_READ_BYTES = 1_000_000

    def __init__(
        self,
        repository: WorkspaceRepository,
        local_storage: WorkspaceLocalStorage,
    ) -> None:
        self._repository = repository
        self._local_storage = local_storage

    def create(self, command: WorkspaceCreateCommand) -> WorkspaceResult:
        """요청 이름을 정규화해 새 워크스페이스를 생성합니다."""
        normalized_name = self._normalize_name(command.name)
        if normalized_name is None:
            raise ValueError("Workspace name must not be empty.")

        workspace = self._repository.create(
            workspace_id=str(uuid4()),
            name=normalized_name,
        )
        self._local_storage.ensure_workspace(workspace.id)
        return self._build_response(workspace)

    def list_workspaces(self) -> list[WorkspaceResult]:
        """저장된 워크스페이스 목록을 응답 모델로 반환합니다."""
        return [
            self._build_response(workspace)
            for workspace in self._repository.list_workspaces()
        ]

    def list_files(
        self,
        *,
        workspace_id: str,
        path: str | None,
        max_entries: int | None = None,
    ) -> WorkspaceFileListResult:
        """워크스페이스 로컬 저장소의 현재 폴더 항목만 조회합니다."""
        self._repository.get(workspace_id)
        normalized_path = self._normalize_relative_path(path)
        limit = self._normalize_limit(
            max_entries,
            default=self._DEFAULT_MAX_ENTRIES,
            maximum=self._MAX_ENTRIES,
        )
        target_path = self._local_storage.resolve_path(
            workspace_id=workspace_id,
            relative_path=normalized_path,
        )
        if not target_path.exists():
            raise FileNotFoundError(normalized_path)
        if not target_path.is_dir():
            raise NotADirectoryError(normalized_path)

        entries, has_more = self._list_file_entries(
            workspace_id=workspace_id,
            target_path=target_path,
            limit=limit,
        )
        return WorkspaceFileListResult(
            workspace_id=workspace_id,
            path=normalized_path,
            entries=entries,
            has_more=has_more,
        )

    def read_file(
        self,
        *,
        workspace_id: str,
        path: str,
        max_bytes: int | None = None,
    ) -> WorkspaceFileContentResult:
        """워크스페이스 로컬 저장소의 텍스트 파일 내용을 읽습니다."""
        self._repository.get(workspace_id)
        normalized_path = self._normalize_required_relative_path(path)
        byte_limit = self._normalize_limit(
            max_bytes,
            default=self._DEFAULT_MAX_READ_BYTES,
            maximum=self._MAX_READ_BYTES,
        )
        target_path = self._local_storage.resolve_path(
            workspace_id=workspace_id,
            relative_path=normalized_path,
        )
        if not target_path.exists():
            raise FileNotFoundError(normalized_path)
        if not target_path.is_file():
            raise IsADirectoryError(normalized_path)

        stat = target_path.stat()
        with target_path.open("rb") as file:
            content_bytes = file.read(byte_limit)
        try:
            content = content_bytes.decode("utf-8")
            is_binary = False
        except UnicodeDecodeError:
            # 프론트 탐색은 read-only 미리보기만 제공하므로 바이너리는 내용을 숨깁니다.
            content = None
            is_binary = True

        return WorkspaceFileContentResult(
            workspace_id=workspace_id,
            path=normalized_path,
            name=target_path.name,
            size_bytes=stat.st_size,
            content=content,
            is_binary=is_binary,
            truncated=stat.st_size > byte_limit,
        )

    def update(
        self, workspace_id: str, command: WorkspaceUpdateCommand
    ) -> WorkspaceResult:
        """워크스페이스 이름을 수정합니다."""
        normalized_name = self._normalize_name(command.name)
        if normalized_name is None:
            raise ValueError("Workspace name must not be empty.")

        workspace = self._repository.update(
            workspace_id=workspace_id,
            name=normalized_name,
        )
        return self._build_response(workspace)

    def delete(self, workspace_id: str) -> WorkspaceDeleteResult:
        """워크스페이스를 삭제합니다."""
        self._repository.delete(workspace_id)
        self._local_storage.delete_workspace(workspace_id)
        return WorkspaceDeleteResult(id=workspace_id, deleted=True)

    def attach_dataset(
        self, *, workspace_id: str, dataset_id: str
    ) -> WorkspaceDatasetLinkResult:
        """워크스페이스와 데이터셋 연결을 저장합니다."""
        dataset_ids = self._repository.attach_dataset(
            workspace_id=workspace_id,
            dataset_id=dataset_id,
        )
        return WorkspaceDatasetLinkResult(
            workspace_id=workspace_id,
            dataset_ids=dataset_ids,
        )

    def list_dataset_ids(self, workspace_id: str) -> WorkspaceDatasetLinkResult:
        """워크스페이스에 연결된 데이터셋 ID 목록을 조회합니다."""
        return WorkspaceDatasetLinkResult(
            workspace_id=workspace_id,
            dataset_ids=self._repository.list_dataset_ids(workspace_id),
        )

    def detach_dataset(
        self, *, workspace_id: str, dataset_id: str
    ) -> WorkspaceDatasetLinkResult:
        """워크스페이스와 데이터셋 연결을 해제합니다."""
        dataset_ids = self._repository.detach_dataset(
            workspace_id=workspace_id,
            dataset_id=dataset_id,
        )
        return WorkspaceDatasetLinkResult(
            workspace_id=workspace_id,
            dataset_ids=dataset_ids,
        )

    def _normalize_name(self, name: str | None) -> str | None:
        """공백을 정리하고 저장 가능한 워크스페이스 이름으로 변환합니다."""
        if name is None:
            return None
        normalized = " ".join(name.strip().split())
        if not normalized:
            return None
        return normalized[:80]

    def _normalize_relative_path(self, path: str | None) -> str:
        """API 입력 경로를 워크스페이스 기준 상대 경로 문자열로 정리합니다."""
        if path is None:
            return ""
        return path.strip().strip("/")

    def _normalize_required_relative_path(self, path: str | None) -> str:
        """필수 파일 경로를 검증하고 정리합니다."""
        normalized = self._normalize_relative_path(path)
        if not normalized:
            raise ValueError("path is required.")
        return normalized

    def _normalize_limit(
        self,
        value: int | None,
        *,
        default: int,
        maximum: int,
    ) -> int:
        """목록/파일 읽기 제한 값을 서버 허용 범위 안으로 맞춥니다."""
        if value is None:
            return default
        return min(max(value, 1), maximum)

    def _list_file_entries(
        self,
        *,
        workspace_id: str,
        target_path: Path,
        limit: int,
    ) -> tuple[list[WorkspaceFileEntryResult], bool]:
        """현재 폴더의 직접 자식 항목을 정렬된 응답 DTO로 변환합니다."""
        workspace_root = self._local_storage.resolve_path(
            workspace_id=workspace_id,
            relative_path="",
        ).resolve()
        children = sorted(
            target_path.iterdir(),
            key=lambda child: (not child.is_dir(), child.name.lower()),
        )
        entries: list[WorkspaceFileEntryResult] = []
        for child in children[:limit]:
            try:
                resolved_child = child.resolve()
                relative_path = resolved_child.relative_to(workspace_root).as_posix()
                stat = child.stat()
            except (OSError, ValueError):
                # 워크스페이스 경계를 벗어나는 심볼릭 링크나 접근 불가 항목은 노출하지 않습니다.
                continue
            entries.append(
                WorkspaceFileEntryResult(
                    path=relative_path,
                    name=child.name,
                    kind="directory" if child.is_dir() else "file",
                    size_bytes=stat.st_size if child.is_file() else None,
                    updated_at=datetime.fromtimestamp(stat.st_mtime, UTC),
                )
            )
        return entries, len(children) > limit

    def _build_response(self, workspace: Workspace) -> WorkspaceResult:
        """domain 모델을 application 출력 DTO로 변환합니다."""
        return WorkspaceResult(
            id=workspace.id,
            name=workspace.name,
            created_at=self._coerce_datetime(workspace.created_at),
            updated_at=self._coerce_datetime(workspace.updated_at),
        )

    def _coerce_datetime(self, value: datetime) -> datetime:
        """SQLite에서 timezone이 사라진 datetime도 응답 모델에 맞게 반환합니다."""
        return value
