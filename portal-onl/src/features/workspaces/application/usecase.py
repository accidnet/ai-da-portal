from datetime import datetime
from uuid import uuid4

from features.workspaces.application.dto import (
    WorkspaceCreateCommand,
    WorkspaceDeleteResult,
    WorkspaceResult,
    WorkspaceUpdateCommand,
)
from features.workspaces.domain.models import Workspace
from features.workspaces.domain.repositories import WorkspaceRepository


class WorkspaceUsecase:
    """워크스페이스 생성과 조회 유스케이스를 수행합니다."""

    def __init__(self, repository: WorkspaceRepository) -> None:
        self._repository = repository

    def create(self, command: WorkspaceCreateCommand) -> WorkspaceResult:
        """요청 이름을 정규화해 새 워크스페이스를 생성합니다."""
        normalized_name = self._normalize_name(command.name)
        if normalized_name is None:
            raise ValueError("Workspace name must not be empty.")

        workspace = self._repository.create(
            workspace_id=str(uuid4()),
            name=normalized_name,
        )
        return self._build_response(workspace)

    def list_workspaces(self) -> list[WorkspaceResult]:
        """저장된 워크스페이스 목록을 응답 모델로 반환합니다."""
        return [
            self._build_response(workspace)
            for workspace in self._repository.list_workspaces()
        ]

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
        return WorkspaceDeleteResult(id=workspace_id, deleted=True)

    def _normalize_name(self, name: str | None) -> str | None:
        """공백을 정리하고 저장 가능한 워크스페이스 이름으로 변환합니다."""
        if name is None:
            return None
        normalized = " ".join(name.strip().split())
        if not normalized:
            return None
        return normalized[:80]

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
