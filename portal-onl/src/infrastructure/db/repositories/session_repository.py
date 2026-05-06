from datetime import UTC, datetime

from infrastructure.db.models import (
    SessionDatasetLinkOrm,
    SessionOrm,
)
from infrastructure.db.session import SessionLocal

from sqlalchemy import select
from sqlalchemy.orm import selectinload


class SessionRepository:
    """세션 관련 ORM 조회와 영속화 작업을 담당합니다."""

    def create(self, *, session_id: str, title: str) -> SessionOrm:
        """새 세션을 생성하고 로드된 ORM 객체를 반환합니다."""
        now = datetime.now(UTC)
        with SessionLocal() as db:
            session = SessionOrm(
                id=session_id,
                title=title,
                preferred_dataset_id=None,
                created_at=now,
                updated_at=now,
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            self._load_relationships(db, session)
            return session

    def list_sessions(self) -> list[SessionOrm]:
        """최신 수정 순서로 세션 목록을 조회합니다."""
        with SessionLocal() as db:
            return list(
                db.scalars(
                    select(SessionOrm)
                    .options(
                        selectinload(SessionOrm.dataset_links),
                    )
                    .order_by(SessionOrm.updated_at.desc())
                ).all()
            )

    def get(self, session_id: str) -> SessionOrm | None:
        """세션 ID로 세션을 조회합니다."""
        with SessionLocal() as db:
            return self._get_session(db, session_id)

    def get_or_raise(self, session_id: str) -> SessionOrm:
        """세션을 조회하고 없으면 KeyError를 발생시킵니다."""
        session = self.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def update_session(
        self,
        *,
        session_id: str,
        title: str | None,
        preferred_dataset_id: str | None,
        update_preferred_dataset: bool,
    ) -> SessionOrm:
        """세션 제목과 선호 데이터셋을 수정합니다."""
        with SessionLocal() as db:
            session = self._get_session_or_raise(db, session_id)
            self._load_relationships(db, session)

            if title is not None:
                session.title = title

            if update_preferred_dataset:
                session.preferred_dataset_id = preferred_dataset_id

            session.updated_at = datetime.now(UTC)
            db.commit()
            db.refresh(session)
            self._load_relationships(db, session)
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
            self._load_relationships(db, session)
            return session

    def delete(self, session_id: str) -> None:
        """세션과 연결된 하위 데이터를 삭제합니다."""
        with SessionLocal() as db:
            session = self._get_session_or_raise(db, session_id)
            db.delete(session)
            db.commit()

    def attach_dataset(self, *, session_id: str, dataset_id: str) -> SessionOrm:
        """세션에 데이터셋을 연결하거나 연결 시각을 갱신합니다."""
        with SessionLocal() as db:
            session = self._get_session_or_raise(db, session_id)
            self._load_relationships(db, session)
            now = datetime.now(UTC)
            self._merge_dataset_ids(session, [dataset_id], now=now)
            self._sync_preferred_dataset(session)
            session.updated_at = now
            db.commit()
            db.refresh(session)
            self._load_relationships(db, session)
            return session

    def detach_dataset(self, *, session_id: str, dataset_id: str) -> SessionOrm:
        """세션에서 데이터셋 연결을 제거합니다."""
        with SessionLocal() as db:
            session = self._get_session_or_raise(db, session_id)
            self._load_relationships(db, session)
            link = next(
                (
                    item
                    for item in session.dataset_links
                    if item.dataset_id == dataset_id
                ),
                None,
            )
            if link is not None:
                db.delete(link)
                db.flush()
                self._load_relationships(db, session)
                if session.preferred_dataset_id == dataset_id:
                    session.preferred_dataset_id = (
                        session.dataset_links[0].dataset_id
                        if session.dataset_links
                        else None
                    )
                session.updated_at = datetime.now(UTC)
                db.commit()
                db.refresh(session)
                self._load_relationships(db, session)
            return session

    def list_linked_sessions(self, dataset_id: str) -> list[SessionDatasetLinkOrm]:
        """데이터셋과 연결된 세션 링크를 최신순으로 조회합니다."""
        with SessionLocal() as db:
            return list(
                db.scalars(
                    select(SessionDatasetLinkOrm)
                    .where(SessionDatasetLinkOrm.dataset_id == dataset_id)
                    .order_by(SessionDatasetLinkOrm.linked_at.desc())
                ).all()
            )

    def record_analysis(
        self,
        *,
        session_id: str,
        dataset_ids: list[str],
        analytics: dict[str, object] | None,
        workspace: dict[str, object] | None,
    ) -> None:
        """분석 결과와 데이터셋 연결 정보를 세션에 저장합니다."""
        with SessionLocal() as db:
            session = self._get_session_or_raise(db, session_id)
            self._load_relationships(db, session)
            now = datetime.now(UTC)
            self._apply_session_payloads(
                session=session,
                dataset_ids=dataset_ids,
                analytics=analytics,
                workspace=workspace,
                now=now,
            )
            db.commit()

    def _get_session(self, db, session_id: str) -> SessionOrm | None:
        return db.scalar(
            select(SessionOrm)
            .options(
                selectinload(SessionOrm.dataset_links),
            )
            .where(SessionOrm.id == session_id)
        )

    def _get_session_or_raise(self, db, session_id: str) -> SessionOrm:
        session = self._get_session(db, session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def _load_relationships(self, db, session: SessionOrm) -> None:
        db.refresh(
            session,
            attribute_names=[
                "dataset_links",
            ],
        )

    def _merge_dataset_ids(
        self,
        session: SessionOrm,
        incoming_ids: list[str],
        *,
        now: datetime,
    ) -> None:
        unique_incoming_ids = [dataset_id for dataset_id in incoming_ids if dataset_id]
        existing_links = {link.dataset_id: link for link in session.dataset_links}

        for dataset_id in unique_incoming_ids:
            link = existing_links.get(dataset_id)
            if link is None:
                session.dataset_links.append(
                    SessionDatasetLinkOrm(dataset_id=dataset_id, linked_at=now)
                )
                continue
            link.linked_at = now

        ordered_dataset_ids: list[str] = []
        for dataset_id in [
            *unique_incoming_ids,
            *[link.dataset_id for link in session.dataset_links],
        ]:
            if dataset_id not in ordered_dataset_ids:
                ordered_dataset_ids.append(dataset_id)

        ordered_links: list[SessionDatasetLinkOrm] = []
        for dataset_id in ordered_dataset_ids:
            link = next(
                (
                    item
                    for item in session.dataset_links
                    if item.dataset_id == dataset_id
                ),
                None,
            )
            if link is not None:
                ordered_links.append(link)
        session.dataset_links[:] = ordered_links

    def _sync_preferred_dataset(self, session: SessionOrm) -> None:
        if session.preferred_dataset_id is None and session.dataset_links:
            session.preferred_dataset_id = session.dataset_links[0].dataset_id

    def _apply_session_payloads(
        self,
        *,
        session: SessionOrm,
        dataset_ids: list[str],
        analytics: dict[str, object] | None,
        workspace: dict[str, object] | None,
        now: datetime,
    ) -> None:
        self._merge_dataset_ids(session, dataset_ids, now=now)
        self._sync_preferred_dataset(session)
        if analytics is not None:
            session.analytics = analytics
        if workspace is not None:
            session.workspace = workspace
        session.updated_at = now
