from datetime import UTC, datetime
import re
from typing import TYPE_CHECKING
from uuid import uuid4

from agents.state import AgentRoute
from domain.shared import AnalyticsPayload
from domain.sessions.schemas import (
    SessionCreateRequest,
    SessionDatasetLinkResponse,
    SessionDeleteResponse,
    SessionDetail,
    SessionLastDataset,
    SessionMessage,
    SessionSnapshotDataset,
    SessionSnapshotResponse,
    SessionSummary,
    SessionUpdateRequest,
)
from domain.shared import WorkspacePayload
from infrastructure.db.models import (
    SessionDatasetLinkOrm,
    SessionMessageOrm,
    SessionOrm,
)
from infrastructure.db.session import SessionLocal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

if TYPE_CHECKING:
    from domain.datasets.service import DatasetService


class SessionService:
    _DEFAULT_TITLE_PATTERNS = (
        re.compile(r"^ChatGPT 분석 세션$", re.IGNORECASE),
        re.compile(r"^New analysis session$", re.IGNORECASE),
        re.compile(r"^분석 세션\s*\d+$"),
        re.compile(r"^Session\s+[A-Za-z0-9-]{4,}$", re.IGNORECASE),
    )

    def __init__(self) -> None:
        self._ensure_seed_session()

    def create(self, payload: SessionCreateRequest) -> SessionDetail:
        session_id = str(uuid4())
        now = datetime.now(UTC)
        with SessionLocal() as db:
            session = SessionOrm(
                id=session_id,
                title=self._normalize_title(payload.title) or "New analysis session",
                preferred_dataset_id=None,
                created_at=now,
                updated_at=now,
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            return self._build_session_detail(session, dataset_service=None)

    def ensure_session(
        self, session_id: str, *, title: str | None = None
    ) -> SessionDetail:
        with SessionLocal() as db:
            session = self._get_session(db, session_id)
            if session is None:
                now = datetime.now(UTC)
                session = SessionOrm(
                    id=session_id,
                    title=self._normalize_title(title) or f"Session {session_id[:8]}",
                    preferred_dataset_id=None,
                    created_at=now,
                    updated_at=now,
                )
                db.add(session)
                db.commit()
                db.refresh(session)
            return self._build_session_detail(session, dataset_service=None)

    def list_sessions(self, dataset_service: "DatasetService") -> list[SessionSummary]:
        with SessionLocal() as db:
            sessions = db.scalars(
                select(SessionOrm)
                .options(
                    selectinload(SessionOrm.messages),
                    selectinload(SessionOrm.dataset_links),
                )
                .order_by(SessionOrm.updated_at.desc())
            ).all()
            return [
                self._build_session_detail(session, dataset_service)
                for session in sessions
            ]

    def get(self, session_id: str) -> SessionDetail:
        with SessionLocal() as db:
            session = self._get_session_or_raise(db, session_id)
            return self._build_session_detail(session, dataset_service=None)

    def get_dataset_ids(self, session_id: str) -> list[str]:
        with SessionLocal() as db:
            session = self._get_session(db, session_id)
            if session is None:
                return []
            self._load_relationships(db, session)
            return [link.dataset_id for link in session.dataset_links]

    def update(self, session_id: str, payload: SessionUpdateRequest) -> SessionDetail:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError(
                "At least one of 'title' or 'preferred_dataset_id' must be provided."
            )

        with SessionLocal() as db:
            session = self._get_session_or_raise(db, session_id)
            self._load_relationships(db, session)

            if "title" in updates:
                normalized_title = self._normalize_title(payload.title)
                if normalized_title is None:
                    raise ValueError("Session title must not be empty.")
                session.title = normalized_title

            if "preferred_dataset_id" in updates:
                preferred_dataset_id = payload.preferred_dataset_id
                linked_dataset_ids = {link.dataset_id for link in session.dataset_links}
                if (
                    preferred_dataset_id is not None
                    and preferred_dataset_id not in linked_dataset_ids
                ):
                    raise ValueError(
                        "Preferred dataset must already be linked to the session."
                    )
                session.preferred_dataset_id = preferred_dataset_id

            session.updated_at = datetime.now(UTC)
            db.commit()
            db.refresh(session)
            self._load_relationships(db, session)
            return self._build_session_detail(session, dataset_service=None)

    def update_title_if_default(self, session_id: str, title: str) -> SessionDetail:
        with SessionLocal() as db:
            session = self._get_or_create_session(db, session_id)
            normalized_title = self._normalize_title(title)
            if normalized_title is None:
                return self._build_session_detail(session, dataset_service=None)
            if not self.is_auto_title_candidate(session.title):
                return self._build_session_detail(session, dataset_service=None)

            session.title = normalized_title
            session.updated_at = datetime.now(UTC)
            db.commit()
            db.refresh(session)
            return self._build_session_detail(session, dataset_service=None)

    def delete(self, session_id: str) -> SessionDeleteResponse:
        with SessionLocal() as db:
            session = self._get_session_or_raise(db, session_id)
            db.delete(session)
            db.commit()
            return SessionDeleteResponse(id=session_id, deleted=True)

    def attach_dataset(
        self, session_id: str, dataset_id: str, *, title: str | None = None
    ) -> SessionDatasetLinkResponse:
        with SessionLocal() as db:
            session = self._get_or_create_session(db, session_id, title=title)
            self._load_relationships(db, session)
            now = datetime.now(UTC)
            self._merge_dataset_ids(session, [dataset_id], now=now)
            self._sync_preferred_dataset(session)
            session.updated_at = now
            db.commit()
            db.refresh(session)
            self._load_relationships(db, session)
            return SessionDatasetLinkResponse(
                session_id=session_id,
                dataset_ids=[link.dataset_id for link in session.dataset_links],
            )

    def detach_dataset(
        self, session_id: str, dataset_id: str
    ) -> SessionDatasetLinkResponse:
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
            return SessionDatasetLinkResponse(
                session_id=session_id,
                dataset_ids=[link.dataset_id for link in session.dataset_links],
            )

    def list_linked_sessions(self, dataset_id: str) -> list[tuple[str, datetime]]:
        with SessionLocal() as db:
            links = db.scalars(
                select(SessionDatasetLinkOrm)
                .where(SessionDatasetLinkOrm.dataset_id == dataset_id)
                .order_by(SessionDatasetLinkOrm.linked_at.desc())
            ).all()
            return [
                (link.session_id, self._coerce_datetime(link.linked_at))
                for link in links
            ]

    def record_chat(
        self,
        *,
        session_id: str,
        user_message: str,
        assistant_message: str,
        route: AgentRoute,
        used_tools: list[str],
        dataset_ids: list[str],
        analytics: AnalyticsPayload | None,
        workspace: WorkspacePayload | None,
    ) -> None:
        with SessionLocal() as db:
            session = self._get_or_create_session(db, session_id)
            self._load_relationships(db, session)
            now = datetime.now(UTC)
            session.messages.extend(
                [
                    SessionMessageOrm(
                        id=str(uuid4()),
                        role="user",
                        text=user_message,
                        created_at=now,
                    ),
                    SessionMessageOrm(
                        id=str(uuid4()),
                        role="assistant",
                        text=assistant_message,
                        created_at=now,
                        route=route,
                        used_tools=used_tools,
                    ),
                ]
            )
            self._merge_dataset_ids(session, dataset_ids, now=now)
            self._sync_preferred_dataset(session)
            if analytics is not None:
                session.analytics = analytics.model_dump(mode="json")
            if workspace is not None:
                session.workspace = workspace.model_dump(mode="json")
            session.updated_at = now
            db.commit()

    def record_analysis(
        self,
        *,
        session_id: str,
        dataset_id: str | None,
        analytics: AnalyticsPayload | None,
        workspace: WorkspacePayload | None,
        title: str | None = None,
    ) -> None:
        with SessionLocal() as db:
            session = self._get_or_create_session(db, session_id, title=title)
            self._load_relationships(db, session)
            now = datetime.now(UTC)
            self._merge_dataset_ids(
                session,
                [dataset_id] if dataset_id else [],
                now=now,
            )
            self._sync_preferred_dataset(session)
            if workspace is not None:
                session.workspace = workspace.model_dump(mode="json")
            if analytics is not None:
                session.analytics = analytics.model_dump(mode="json")
            session.updated_at = now
            db.commit()

    def get_snapshot(
        self, session_id: str, dataset_service: "DatasetService"
    ) -> SessionSnapshotResponse:
        with SessionLocal() as db:
            session = self._get_session_or_raise(db, session_id)
            self._load_relationships(db, session)
            datasets: list[SessionSnapshotDataset] = []
            for link in session.dataset_links:
                try:
                    datasets.append(
                        SessionSnapshotDataset(
                            detail=dataset_service.get(link.dataset_id),
                            preview=dataset_service.get_preview(link.dataset_id),
                            profile=dataset_service.get_profile(link.dataset_id),
                        )
                    )
                except KeyError:
                    continue

            return SessionSnapshotResponse(
                session=self._build_session_detail(session, dataset_service),
                messages=[self._build_message(message) for message in session.messages],
                dataset_ids=[link.dataset_id for link in session.dataset_links],
                datasets=datasets,
                analytics=self._build_analytics(session.analytics),
                workspace=self._build_workspace(session.workspace),
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

    def _normalize_title(self, title: str | None) -> str | None:
        if title is None:
            return None
        normalized = " ".join(title.strip().split())
        if not normalized:
            return None
        return normalized[:60]

    def is_auto_title_candidate(self, title: str | None) -> bool:
        normalized = self._normalize_title(title)
        if normalized is None:
            return True
        return any(
            pattern.fullmatch(normalized) for pattern in self._DEFAULT_TITLE_PATTERNS
        )

    def _build_session_detail(
        self, session: SessionOrm, dataset_service: "DatasetService | None"
    ) -> SessionDetail:
        last_dataset = self._build_last_dataset(session, dataset_service)
        return SessionDetail(
            id=session.id,
            title=session.title,
            created_at=self._coerce_datetime(session.created_at),
            updated_at=self._coerce_datetime(session.updated_at),
            preferred_dataset_id=session.preferred_dataset_id,
            message_count=len(session.messages),
            dataset_count=len(session.dataset_links),
            last_dataset=last_dataset,
        )

    def hydrate_session_detail(
        self, session_id: str, dataset_service: "DatasetService"
    ) -> SessionDetail:
        with SessionLocal() as db:
            session = self._get_session_or_raise(db, session_id)
            self._load_relationships(db, session)
            return self._build_session_detail(session, dataset_service)

    def _build_last_dataset(
        self, session: SessionOrm, dataset_service: "DatasetService | None"
    ) -> SessionLastDataset | None:
        if dataset_service is None or not session.dataset_links:
            return None
        last_dataset_id = session.dataset_links[0].dataset_id
        try:
            dataset = dataset_service.get(last_dataset_id)
        except KeyError:
            return None
        return SessionLastDataset(id=dataset.id, filename=dataset.filename)

    def _ensure_seed_session(self) -> None:
        with SessionLocal() as db:
            if self._get_session(db, "demo-session") is not None:
                return
            now = datetime.now(UTC)
            db.add(
                SessionOrm(
                    id="demo-session",
                    title="Marketing performance review",
                    preferred_dataset_id=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            db.commit()

    def _get_session(self, db, session_id: str) -> SessionOrm | None:
        return db.scalar(
            select(SessionOrm)
            .options(
                selectinload(SessionOrm.messages),
                selectinload(SessionOrm.dataset_links),
            )
            .where(SessionOrm.id == session_id)
        )

    def _get_session_or_raise(self, db, session_id: str) -> SessionOrm:
        session = self._get_session(db, session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def _get_or_create_session(
        self, db, session_id: str, *, title: str | None = None
    ) -> SessionOrm:
        session = self._get_session(db, session_id)
        if session is not None:
            return session

        now = datetime.now(UTC)
        session = SessionOrm(
            id=session_id,
            title=self._normalize_title(title) or f"Session {session_id[:8]}",
            preferred_dataset_id=None,
            created_at=now,
            updated_at=now,
        )
        db.add(session)
        db.flush()
        self._load_relationships(db, session)
        return session

    def _load_relationships(self, db, session: SessionOrm) -> None:
        db.refresh(session, attribute_names=["messages", "dataset_links"])

    def _sync_preferred_dataset(self, session: SessionOrm) -> None:
        if session.preferred_dataset_id is None and session.dataset_links:
            session.preferred_dataset_id = session.dataset_links[0].dataset_id

    def _build_message(self, message: SessionMessageOrm) -> SessionMessage:
        return SessionMessage(
            id=message.id,
            role=message.role,
            text=message.text,
            created_at=self._coerce_datetime(message.created_at),
            route=message.route,
            used_tools=message.used_tools or [],
        )

    def _build_analytics(
        self, payload: dict[str, object] | None
    ) -> AnalyticsPayload | None:
        if payload is None:
            return None
        return AnalyticsPayload.model_validate(payload)

    def _build_workspace(
        self, payload: dict[str, object] | None
    ) -> WorkspacePayload | None:
        if payload is None:
            return None
        return WorkspacePayload.model_validate(payload)

    def _coerce_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)
