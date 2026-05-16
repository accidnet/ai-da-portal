from datetime import UTC, datetime

from sqlalchemy import delete, select

from infrastructure.db.models import SessionOrm, WorkspaceDatasetLinkOrm
from infrastructure.db.session import SessionLocal


class SessionRepository:
    """세션 ORM 조회와 영속화 작업을 담당합니다."""

    def create(
        self, *, session_id: str, title: str, workspace_id: str | None = None
    ) -> SessionOrm:
        """새 세션을 생성하고 로드된 ORM 객체를 반환합니다."""
        now = datetime.now(UTC)
        with SessionLocal() as db:
            session = SessionOrm(
                id=session_id,
                workspace_id=workspace_id,
                title=title,
                created_at=now,
                updated_at=now,
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            return session

    def list_sessions(self, *, workspace_id: str | None = None) -> list[SessionOrm]:
        """최신 수정 순서로 세션 목록을 조회합니다."""
        statement = select(SessionOrm).order_by(SessionOrm.updated_at.desc())
        if workspace_id is not None:
            statement = statement.where(SessionOrm.workspace_id == workspace_id)

        with SessionLocal() as db:
            return list(db.scalars(statement).all())

    def get(self, session_id: str) -> SessionOrm | None:
        """세션 ID로 세션을 조회합니다."""
        with SessionLocal() as db:
            return db.scalar(select(SessionOrm).where(SessionOrm.id == session_id))

    def get_or_raise(self, session_id: str) -> SessionOrm:
        """세션을 조회하고 없으면 KeyError를 발생시킵니다."""
        session = self.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def update_session(self, *, session_id: str, title: str | None) -> SessionOrm:
        """세션 제목을 수정합니다."""
        with SessionLocal() as db:
            session = self._get_session_or_raise(db, session_id)
            if title is not None:
                session.title = title
            session.updated_at = datetime.now(UTC)
            db.commit()
            db.refresh(session)
            return session

    def update_title_if_current(
        self, *, session_id: str, current_title: str, title: str
    ) -> SessionOrm:
        """현재 제목이 일치할 때만 제목을 갱신합니다."""
        with SessionLocal() as db:
            session = self._get_session_or_raise(db, session_id)
            if session.title == current_title:
                session.title = title
                session.updated_at = datetime.now(UTC)
                db.commit()
                db.refresh(session)
            return session

    def touch(self, session_id: str) -> None:
        """세션의 갱신 시각만 업데이트합니다."""
        with SessionLocal() as db:
            session = self._get_session_or_raise(db, session_id)
            session.updated_at = datetime.now(UTC)
            db.commit()

    def delete(self, session_id: str) -> None:
        """세션과 연결된 하위 데이터를 삭제합니다."""
        with SessionLocal() as db:
            session = self._get_session_or_raise(db, session_id)
            db.delete(session)
            db.commit()

    def attach_dataset(self, *, session_id: str, dataset_id: str) -> list[str]:
        """세션이 속한 워크스페이스와 데이터셋 연결 row를 생성합니다."""
        now = datetime.now(UTC)
        with SessionLocal() as db:
            session = self._get_session_or_raise(db, session_id)
            if session.workspace_id is None:
                raise ValueError("Session is not associated with a workspace.")
            link = db.scalar(
                select(WorkspaceDatasetLinkOrm).where(
                    WorkspaceDatasetLinkOrm.workspace_id == session.workspace_id,
                    WorkspaceDatasetLinkOrm.dataset_id == dataset_id,
                )
            )
            if link is None:
                db.add(
                    WorkspaceDatasetLinkOrm(
                        workspace_id=session.workspace_id,
                        dataset_id=dataset_id,
                        linked_at=now,
                    )
                )
            else:
                link.linked_at = now
            session.updated_at = now
            db.commit()
        return self.list_session_dataset_ids(session_id)

    def detach_dataset(self, *, session_id: str, dataset_id: str) -> list[str]:
        """세션이 속한 워크스페이스와 데이터셋 연결 row를 제거합니다."""
        with SessionLocal() as db:
            session = self._get_session_or_raise(db, session_id)
            if session.workspace_id is None:
                raise ValueError("Session is not associated with a workspace.")
            db.execute(
                delete(WorkspaceDatasetLinkOrm).where(
                    WorkspaceDatasetLinkOrm.workspace_id == session.workspace_id,
                    WorkspaceDatasetLinkOrm.dataset_id == dataset_id,
                )
            )
            session.updated_at = datetime.now(UTC)
            db.commit()
        return self.list_session_dataset_ids(session_id)

    def list_session_dataset_ids(self, session_id: str) -> list[str]:
        """세션이 속한 워크스페이스에 연결된 데이터셋 ID를 조회합니다."""
        with SessionLocal() as db:
            session = self._get_session_or_raise(db, session_id)
            if session.workspace_id is None:
                return []
            return list(
                db.scalars(
                    select(WorkspaceDatasetLinkOrm.dataset_id)
                    .where(WorkspaceDatasetLinkOrm.workspace_id == session.workspace_id)
                    .order_by(WorkspaceDatasetLinkOrm.linked_at.desc())
                ).all()
            )

    def list_linked_sessions(self, dataset_id: str) -> list[tuple[str, datetime]]:
        """워크스페이스 연결 기준으로 해당 워크스페이스의 세션을 최신순 조회합니다."""
        with SessionLocal() as db:
            return list(
                db.execute(
                    select(
                        SessionOrm.id,
                        WorkspaceDatasetLinkOrm.linked_at,
                    )
                    .join(
                        WorkspaceDatasetLinkOrm,
                        WorkspaceDatasetLinkOrm.workspace_id == SessionOrm.workspace_id,
                    )
                    .where(WorkspaceDatasetLinkOrm.dataset_id == dataset_id)
                    .order_by(WorkspaceDatasetLinkOrm.linked_at.desc())
                ).all()
            )

    def _get_session_or_raise(self, db, session_id: str) -> SessionOrm:
        session = db.scalar(select(SessionOrm).where(SessionOrm.id == session_id))
        if session is None:
            raise KeyError(session_id)
        return session
