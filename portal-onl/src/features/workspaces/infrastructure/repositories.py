from datetime import UTC, datetime

from sqlalchemy import select

from features.workspaces.domain.models import Workspace
from features.workspaces.infrastructure.orm import WorkspaceOrm
from infrastructure.db.session import SessionLocal


class WorkspaceRepository:
    """워크스페이스 ORM 조회와 영속화 작업을 담당합니다."""

    def create(self, *, workspace_id: str, name: str) -> Workspace:
        """새 워크스페이스를 생성하고 domain 모델을 반환합니다."""
        now = datetime.now(UTC)
        with SessionLocal() as db:
            workspace = WorkspaceOrm(
                id=workspace_id,
                name=name,
                created_at=now,
                updated_at=now,
            )
            db.add(workspace)
            db.commit()
            db.refresh(workspace)
            return self._to_domain(workspace)

    def list_workspaces(self) -> list[Workspace]:
        """최신 생성 순서로 워크스페이스 목록을 조회합니다."""
        with SessionLocal() as db:
            workspaces = list(
                db.scalars(
                    select(WorkspaceOrm).order_by(WorkspaceOrm.created_at.desc())
                ).all()
            )
            return [self._to_domain(workspace) for workspace in workspaces]

    def update(self, *, workspace_id: str, name: str) -> Workspace:
        """워크스페이스 이름을 수정하고 갱신된 domain 모델을 반환합니다."""
        with SessionLocal() as db:
            workspace = self._get_workspace_or_raise(db, workspace_id)
            workspace.name = name
            workspace.updated_at = datetime.now(UTC)
            db.commit()
            db.refresh(workspace)
            return self._to_domain(workspace)

    def delete(self, workspace_id: str) -> None:
        """워크스페이스를 삭제합니다."""
        with SessionLocal() as db:
            workspace = self._get_workspace_or_raise(db, workspace_id)
            db.delete(workspace)
            db.commit()

    def _get_workspace_or_raise(self, db, workspace_id: str) -> WorkspaceOrm:
        """워크스페이스를 조회하고 없으면 KeyError를 발생시킵니다."""
        workspace = db.scalar(
            select(WorkspaceOrm).where(WorkspaceOrm.id == workspace_id)
        )
        if workspace is None:
            raise KeyError(workspace_id)
        return workspace

    def _to_domain(self, workspace: WorkspaceOrm) -> Workspace:
        """ORM 모델을 domain 모델로 변환합니다."""
        return Workspace(
            id=workspace.id,
            name=workspace.name,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )
