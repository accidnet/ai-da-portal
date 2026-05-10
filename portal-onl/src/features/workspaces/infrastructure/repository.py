from datetime import UTC, datetime

from sqlalchemy import select

from features.workspaces.infrastructure.models import WorkspaceOrm
from infrastructure.db.session import SessionLocal


class WorkspaceRepository:
    """워크스페이스 ORM 조회와 영속화 작업을 담당합니다."""

    def create(self, *, workspace_id: str, name: str) -> WorkspaceOrm:
        """새 워크스페이스를 생성하고 로드된 ORM 객체를 반환합니다."""
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
            return workspace

    def list_workspaces(self) -> list[WorkspaceOrm]:
        """최신 생성 순서로 워크스페이스 목록을 조회합니다."""
        with SessionLocal() as db:
            return list(
                db.scalars(
                    select(WorkspaceOrm).order_by(WorkspaceOrm.created_at.desc())
                ).all()
            )
