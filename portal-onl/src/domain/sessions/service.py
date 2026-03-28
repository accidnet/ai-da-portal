from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from domain.shared import AnalyticsPayload
from domain.sessions.schemas import (
    SessionCreateRequest,
    SessionDetail,
    SessionMessage,
    SessionSnapshotDataset,
    SessionSnapshotResponse,
    SessionSummary,
    SessionWorkspace,
)

if TYPE_CHECKING:
    from domain.datasets.service import DatasetService


class SessionService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self._sessions: dict[str, _SessionRecord] = {
            "demo-session": _SessionRecord(
                detail=SessionDetail(
                    id="demo-session",
                    title="Marketing performance review",
                    created_at=now,
                    updated_at=now,
                )
            )
        }

    def create(self, payload: SessionCreateRequest) -> SessionDetail:
        now = datetime.now(UTC)
        session_id = str(uuid4())
        session = SessionDetail(
            id=session_id, title=payload.title, created_at=now, updated_at=now
        )
        self._sessions[session_id] = _SessionRecord(detail=session)
        return session

    def ensure_session(
        self, session_id: str, *, title: str | None = None
    ) -> SessionDetail:
        record = self._sessions.get(session_id)
        if record is not None:
            return record.detail

        now = datetime.now(UTC)
        session = SessionDetail(
            id=session_id,
            title=self._normalize_title(title) or f"Session {session_id[:8]}",
            created_at=now,
            updated_at=now,
        )
        self._sessions[session_id] = _SessionRecord(detail=session)
        return session

    def list_sessions(self) -> list[SessionSummary]:
        return sorted(
            [
                SessionSummary(
                    id=record.detail.id,
                    title=record.detail.title,
                    updated_at=record.detail.updated_at,
                )
                for record in self._sessions.values()
            ],
            key=lambda session: session.updated_at,
            reverse=True,
        )

    def get(self, session_id: str) -> SessionDetail:
        return self._get_record(session_id).detail

    def get_dataset_ids(self, session_id: str) -> list[str]:
        record = self._sessions.get(session_id)
        if record is None:
            return []
        return list(record.dataset_ids)

    def attach_dataset(
        self, session_id: str, dataset_id: str, *, title: str | None = None
    ) -> None:
        record = self._get_or_create_record(session_id, title=title)
        record.dataset_ids = self._merge_dataset_ids(record.dataset_ids, [dataset_id])
        now = datetime.now(UTC)
        record.workspace = SessionWorkspace(
            session_id=session_id,
            dataset_ids=list(record.dataset_ids),
            primary_dataset_id=dataset_id,
            updated_at=now,
        )
        self._touch(record, now=now)

    def record_chat(
        self,
        *,
        session_id: str,
        user_message: str,
        assistant_message: str,
        dataset_ids: list[str],
        analytics: AnalyticsPayload | None,
        workspace: SessionWorkspace | None,
    ) -> None:
        record = self._get_or_create_record(session_id, title=user_message)
        now = datetime.now(UTC)
        record.messages.extend(
            [
                SessionMessage(
                    id=str(uuid4()),
                    role="user",
                    text=user_message,
                    created_at=now,
                ),
                SessionMessage(
                    id=str(uuid4()),
                    role="assistant",
                    text=assistant_message,
                    created_at=now,
                ),
            ]
        )
        record.dataset_ids = self._merge_dataset_ids(record.dataset_ids, dataset_ids)
        if analytics is not None:
            record.analytics = analytics
        if workspace is not None:
            record.workspace = workspace.model_copy(
                update={
                    "dataset_ids": self._merge_dataset_ids(
                        record.dataset_ids,
                        workspace.dataset_ids,
                    ),
                    "updated_at": now,
                }
            )
        elif record.dataset_ids:
            record.workspace = SessionWorkspace(
                session_id=session_id,
                dataset_ids=list(record.dataset_ids),
                primary_dataset_id=record.dataset_ids[0],
                updated_at=now,
            )
        self._touch(record, now=now)

    def record_analysis(
        self,
        *,
        session_id: str,
        dataset_id: str | None,
        analysis_id: str,
        analysis_type: str,
        analytics: AnalyticsPayload | None,
        title: str | None = None,
    ) -> SessionWorkspace:
        record = self._get_or_create_record(session_id, title=title)
        record.dataset_ids = self._merge_dataset_ids(
            record.dataset_ids,
            [dataset_id] if dataset_id else [],
        )
        now = datetime.now(UTC)
        workspace = SessionWorkspace(
            session_id=session_id,
            dataset_ids=list(record.dataset_ids),
            primary_dataset_id=dataset_id,
            analysis_id=analysis_id,
            analysis_type=analysis_type,
            updated_at=now,
        )
        record.workspace = workspace
        if analytics is not None:
            record.analytics = analytics
        self._touch(record, now=now)
        return workspace

    def get_snapshot(
        self, session_id: str, dataset_service: "DatasetService"
    ) -> SessionSnapshotResponse:
        record = self._get_record(session_id)
        datasets: list[SessionSnapshotDataset] = []
        for dataset_id in record.dataset_ids:
            try:
                datasets.append(
                    SessionSnapshotDataset(
                        detail=dataset_service.get(dataset_id),
                        preview=dataset_service.get_preview(dataset_id),
                        profile=dataset_service.get_profile(dataset_id),
                    )
                )
            except KeyError:
                continue

        return SessionSnapshotResponse(
            session=record.detail,
            messages=list(record.messages),
            dataset_ids=list(record.dataset_ids),
            datasets=datasets,
            analytics=record.analytics,
            workspace=record.workspace,
        )

    def _get_record(self, session_id: str) -> "_SessionRecord":
        record = self._sessions.get(session_id)
        if record is None:
            raise KeyError(session_id)
        return record

    def _get_or_create_record(
        self, session_id: str, *, title: str | None = None
    ) -> "_SessionRecord":
        record = self._sessions.get(session_id)
        if record is not None:
            if self._should_update_title(record.detail.title) and title:
                record.detail = record.detail.model_copy(
                    update={
                        "title": self._normalize_title(title) or record.detail.title
                    }
                )
            return record

        self.ensure_session(session_id, title=title)
        return self._sessions[session_id]

    def _touch(self, record: "_SessionRecord", *, now: datetime | None = None) -> None:
        timestamp = now or datetime.now(UTC)
        record.detail = record.detail.model_copy(update={"updated_at": timestamp})

    def _merge_dataset_ids(
        self, current_ids: list[str], incoming_ids: list[str]
    ) -> list[str]:
        merged: list[str] = []
        for dataset_id in [*incoming_ids, *current_ids]:
            if dataset_id and dataset_id not in merged:
                merged.append(dataset_id)
        return merged

    def _normalize_title(self, title: str | None) -> str | None:
        if title is None:
            return None
        normalized = " ".join(title.strip().split())
        if not normalized:
            return None
        return normalized[:60]

    def _should_update_title(self, title: str) -> bool:
        return title.startswith("Session ")


@dataclass(slots=True)
class _SessionRecord:
    detail: SessionDetail
    messages: list[SessionMessage] = field(default_factory=list)
    dataset_ids: list[str] = field(default_factory=list)
    analytics: AnalyticsPayload | None = None
    workspace: SessionWorkspace | None = None
