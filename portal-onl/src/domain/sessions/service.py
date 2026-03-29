from dataclasses import dataclass, field
from datetime import UTC, datetime
import re
from typing import TYPE_CHECKING
from uuid import uuid4

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
        now = datetime.now(UTC)
        self._sessions: dict[str, _SessionRecord] = {
            "demo-session": _SessionRecord(
                detail=SessionDetail(
                    id="demo-session",
                    title="Marketing performance review",
                    created_at=now,
                    updated_at=now,
                    preferred_dataset_id=None,
                    message_count=0,
                    dataset_count=0,
                    last_dataset=None,
                )
            )
        }

    def create(self, payload: SessionCreateRequest) -> SessionDetail:
        now = datetime.now(UTC)
        session_id = str(uuid4())
        session = SessionDetail(
            id=session_id,
            title=payload.title,
            created_at=now,
            updated_at=now,
            preferred_dataset_id=None,
            message_count=0,
            dataset_count=0,
            last_dataset=None,
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
            preferred_dataset_id=None,
            message_count=0,
            dataset_count=0,
            last_dataset=None,
        )
        self._sessions[session_id] = _SessionRecord(detail=session)
        return session

    def list_sessions(self, dataset_service: "DatasetService") -> list[SessionSummary]:
        return sorted(
            [
                self._build_session_detail(record, dataset_service)
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

    def update(self, session_id: str, payload: SessionUpdateRequest) -> SessionDetail:
        record = self._get_record(session_id)
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError(
                "At least one of 'title' or 'preferred_dataset_id' must be provided."
            )

        detail_updates: dict[str, str | None] = {}
        if "title" in updates:
            normalized_title = self._normalize_title(payload.title)
            if normalized_title is None:
                raise ValueError("Session title must not be empty.")
            detail_updates["title"] = normalized_title

        if "preferred_dataset_id" in updates:
            preferred_dataset_id = payload.preferred_dataset_id
            if (
                preferred_dataset_id is not None
                and preferred_dataset_id not in record.dataset_ids
            ):
                raise ValueError(
                    "Preferred dataset must already be linked to the session."
                )
            detail_updates["preferred_dataset_id"] = preferred_dataset_id

        record.detail = record.detail.model_copy(update=detail_updates)
        self._touch(record)
        return record.detail

    def update_title_if_default(self, session_id: str, title: str) -> SessionDetail:
        record = self._get_or_create_record(session_id)
        normalized_title = self._normalize_title(title)
        if normalized_title is None:
            return record.detail
        if not self.is_auto_title_candidate(record.detail.title):
            return record.detail

        record.detail = record.detail.model_copy(update={"title": normalized_title})
        self._touch(record)
        return record.detail

    def delete(self, session_id: str) -> SessionDeleteResponse:
        self._get_record(session_id)
        del self._sessions[session_id]
        return SessionDeleteResponse(id=session_id, deleted=True)

    def attach_dataset(
        self, session_id: str, dataset_id: str, *, title: str | None = None
    ) -> SessionDatasetLinkResponse:
        record = self._get_or_create_record(session_id, title=title)
        now = datetime.now(UTC)
        self._merge_dataset_ids(record, [dataset_id], now=now)
        self._sync_preferred_dataset(record)
        self._touch(record, now=now)
        return SessionDatasetLinkResponse(
            session_id=session_id,
            dataset_ids=list(record.dataset_ids),
        )

    def detach_dataset(
        self, session_id: str, dataset_id: str
    ) -> SessionDatasetLinkResponse:
        record = self._get_record(session_id)
        if dataset_id in record.dataset_ids:
            record.dataset_ids = [
                item for item in record.dataset_ids if item != dataset_id
            ]
            record.dataset_timestamps.pop(dataset_id, None)
            if record.detail.preferred_dataset_id == dataset_id:
                replacement_dataset_id = (
                    record.dataset_ids[0] if record.dataset_ids else None
                )
                record.detail = record.detail.model_copy(
                    update={"preferred_dataset_id": replacement_dataset_id}
                )
            self._touch(record)
        return SessionDatasetLinkResponse(
            session_id=session_id,
            dataset_ids=list(record.dataset_ids),
        )

    def list_linked_sessions(self, dataset_id: str) -> list[tuple[str, datetime]]:
        linked_sessions: list[tuple[str, datetime]] = []
        for session_id, record in self._sessions.items():
            linked_at = record.dataset_timestamps.get(dataset_id)
            if linked_at is not None:
                linked_sessions.append((session_id, linked_at))
        linked_sessions.sort(key=lambda item: item[1], reverse=True)
        return linked_sessions

    def record_chat(
        self,
        *,
        session_id: str,
        user_message: str,
        assistant_message: str,
        dataset_ids: list[str],
        analytics: AnalyticsPayload | None,
        workspace: WorkspacePayload | None,
    ) -> None:
        record = self._get_or_create_record(session_id)
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
        self._merge_dataset_ids(record, dataset_ids, now=now)
        self._sync_preferred_dataset(record)
        if analytics is not None:
            record.analytics = analytics
        if workspace is not None:
            record.workspace = workspace
        self._touch(record, now=now)

    def record_analysis(
        self,
        *,
        session_id: str,
        dataset_id: str | None,
        analytics: AnalyticsPayload | None,
        workspace: WorkspacePayload | None,
        title: str | None = None,
    ) -> None:
        record = self._get_or_create_record(session_id, title=title)
        now = datetime.now(UTC)
        self._merge_dataset_ids(
            record,
            [dataset_id] if dataset_id else [],
            now=now,
        )
        self._sync_preferred_dataset(record)
        if workspace is not None:
            record.workspace = workspace
        if analytics is not None:
            record.analytics = analytics
        self._touch(record, now=now)

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
            session=self._build_session_detail(record, dataset_service),
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
            return record

        self.ensure_session(session_id, title=title)
        return self._sessions[session_id]

    def _touch(self, record: "_SessionRecord", *, now: datetime | None = None) -> None:
        timestamp = now or datetime.now(UTC)
        record.detail = record.detail.model_copy(update={"updated_at": timestamp})

    def _merge_dataset_ids(
        self,
        record: "_SessionRecord",
        incoming_ids: list[str],
        *,
        now: datetime,
    ) -> None:
        merged: list[str] = []
        for dataset_id in [*incoming_ids, *record.dataset_ids]:
            if dataset_id and dataset_id not in merged:
                merged.append(dataset_id)
        for dataset_id in incoming_ids:
            if dataset_id:
                record.dataset_timestamps[dataset_id] = now
        record.dataset_ids = merged

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

    def _sync_preferred_dataset(self, record: "_SessionRecord") -> None:
        if record.detail.preferred_dataset_id is None and record.dataset_ids:
            record.detail = record.detail.model_copy(
                update={"preferred_dataset_id": record.dataset_ids[0]}
            )

    def _build_session_detail(
        self, record: "_SessionRecord", dataset_service: "DatasetService"
    ) -> SessionDetail:
        last_dataset = self._build_last_dataset(record, dataset_service)
        return record.detail.model_copy(
            update={
                "message_count": len(record.messages),
                "dataset_count": len(record.dataset_ids),
                "last_dataset": last_dataset,
            }
        )

    def hydrate_session_detail(
        self, session_id: str, dataset_service: "DatasetService"
    ) -> SessionDetail:
        return self._build_session_detail(self._get_record(session_id), dataset_service)

    def _build_last_dataset(
        self, record: "_SessionRecord", dataset_service: "DatasetService"
    ) -> SessionLastDataset | None:
        if not record.dataset_ids:
            return None
        last_dataset_id = record.dataset_ids[0]
        try:
            dataset = dataset_service.get(last_dataset_id)
        except KeyError:
            return None
        return SessionLastDataset(id=dataset.id, filename=dataset.filename)


@dataclass(slots=True)
class _SessionRecord:
    detail: SessionDetail
    messages: list[SessionMessage] = field(default_factory=list)
    dataset_ids: list[str] = field(default_factory=list)
    dataset_timestamps: dict[str, datetime] = field(default_factory=dict)
    analytics: AnalyticsPayload | None = None
    workspace: WorkspacePayload | None = None
