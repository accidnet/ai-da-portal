from datetime import UTC, datetime

from sqlalchemy import delete, select

from features.workspaces.domain.models import Workspace
from features.workspaces.infrastructure.orm import WorkspaceOrm
from infrastructure.db.models import WorkspaceDatasetLinkOrm
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

    def attach_dataset(self, *, workspace_id: str, dataset_id: str) -> list[str]:
        """워크스페이스에 데이터셋 연결 row를 저장합니다."""
        now = datetime.now(UTC)
        with SessionLocal() as db:
            workspace = self._get_workspace_or_raise(db, workspace_id)
            link = db.scalar(
                select(WorkspaceDatasetLinkOrm).where(
                    WorkspaceDatasetLinkOrm.workspace_id == workspace_id,
                    WorkspaceDatasetLinkOrm.dataset_id == dataset_id,
                )
            )
            if link is None:
                db.add(
                    WorkspaceDatasetLinkOrm(
                        workspace_id=workspace_id,
                        dataset_id=dataset_id,
                        linked_at=now,
                    )
                )
            else:
                link.linked_at = now
            workspace.updated_at = now
            db.commit()
        return self.list_dataset_ids(workspace_id)

    def detach_dataset(self, *, workspace_id: str, dataset_id: str) -> list[str]:
        """워크스페이스의 데이터셋 연결 row를 제거합니다."""
        with SessionLocal() as db:
            workspace = self._get_workspace_or_raise(db, workspace_id)
            db.execute(
                delete(WorkspaceDatasetLinkOrm).where(
                    WorkspaceDatasetLinkOrm.workspace_id == workspace_id,
                    WorkspaceDatasetLinkOrm.dataset_id == dataset_id,
                )
            )
            workspace.updated_at = datetime.now(UTC)
            db.commit()
        return self.list_dataset_ids(workspace_id)

    def list_dataset_ids(self, workspace_id: str) -> list[str]:
        """워크스페이스에 연결된 데이터셋 ID를 최신 연결 순서로 반환합니다."""
        with SessionLocal() as db:
            self._get_workspace_or_raise(db, workspace_id)
            return list(
                db.scalars(
                    select(WorkspaceDatasetLinkOrm.dataset_id)
                    .where(WorkspaceDatasetLinkOrm.workspace_id == workspace_id)
                    .order_by(WorkspaceDatasetLinkOrm.linked_at.desc())
                ).all()
            )

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
