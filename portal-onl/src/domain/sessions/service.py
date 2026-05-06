from datetime import UTC, datetime
import re
from typing import Protocol
from uuid import uuid4

from domain.datasets.schemas import (
    DatasetInfo,
    DatasetPreviewResponse,
    DatasetProfileResponse,
)
from domain.shared import AnalyticsPayload, WorkspacePayload
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
from infrastructure.db.models import (
    BotResponseOrm,
    SessionMessageOrm,
    SessionOrm,
    UserMessageOrm,
)
from infrastructure.db.repositories import MessageRepository, SessionRepository


class _SessionDatasetReader(Protocol):
    """세션 스냅샷 생성에 필요한 데이터셋 조회 인터페이스입니다."""

    def get(self, dataset_id: str) -> DatasetInfo: ...

    def get_preview(self, dataset_id: str) -> DatasetPreviewResponse: ...

    def get_profile(self, dataset_id: str) -> DatasetProfileResponse: ...


class SessionService:
    """세션, 세션 메시지, 데이터셋 연결 정보를 관리합니다."""

    _DEFAULT_TITLE_PATTERNS = (
        re.compile(r"^ChatGPT 분석 세션$", re.IGNORECASE),
        re.compile(r"^New analysis session$", re.IGNORECASE),
        re.compile(r"^분석 세션\s*\d+$"),
        re.compile(r"^Session\s+[A-Za-z0-9-]{4,}$", re.IGNORECASE),
    )

    def __init__(
        self,
        repository: SessionRepository,
        message_repository: MessageRepository,
    ) -> None:
        self._repository = repository
        self._message_repository = message_repository
        self._repository.ensure_seed_session()

    def create(self, payload: SessionCreateRequest) -> SessionDetail:
        session_id = str(uuid4())
        session = self._repository.create(
            session_id=session_id,
            title=self._normalize_title(payload.title) or "New analysis session",
        )
        return self._build_session_detail(session, dataset_service=None)

    def ensure_session(
        self, session_id: str, *, title: str | None = None
    ) -> SessionDetail:
        session = self._get_session(session_id)
        if session is None:
            session = self._create_session(session_id, title=title)
        return self._build_session_detail(session, dataset_service=None)

    def list_sessions(
        self, dataset_service: "_SessionDatasetReader"
    ) -> list[SessionSummary]:
        sessions = self._repository.list_sessions()
        return [
            self._build_session_detail(session, dataset_service) for session in sessions
        ]

    def get(self, session_id: str) -> SessionDetail:
        session = self._repository.get_or_raise(session_id)
        return self._build_session_detail(session, dataset_service=None)

    def get_dataset_ids(self, session_id: str) -> list[str]:
        session = self._repository.get(session_id)
        if session is None:
            return []
        return [link.dataset_id for link in session.dataset_links]

    def update(self, session_id: str, payload: SessionUpdateRequest) -> SessionDetail:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError(
                "At least one of 'title' or 'preferred_dataset_id' must be provided."
            )

        session = self._repository.get_or_raise(session_id)
        normalized_title: str | None = None
        if "title" in updates:
            normalized_title = self._normalize_title(payload.title)
            if normalized_title is None:
                raise ValueError("Session title must not be empty.")

        update_preferred_dataset = "preferred_dataset_id" in updates
        if update_preferred_dataset:
            preferred_dataset_id = payload.preferred_dataset_id
            linked_dataset_ids = {link.dataset_id for link in session.dataset_links}
            if (
                preferred_dataset_id is not None
                and preferred_dataset_id not in linked_dataset_ids
            ):
                raise ValueError(
                    "Preferred dataset must already be linked to the session."
                )

        updated_session = self._repository.update_session(
            session_id=session_id,
            title=normalized_title,
            preferred_dataset_id=payload.preferred_dataset_id,
            update_preferred_dataset=update_preferred_dataset,
        )
        return self._build_session_detail(updated_session, dataset_service=None)

    def update_title_if_default(self, session_id: str, title: str) -> SessionDetail:
        session = self._get_session(session_id)
        if session is None:
            session = self._create_session(session_id)
        normalized_title = self._normalize_title(title)
        if normalized_title is None:
            return self._build_session_detail(session, dataset_service=None)
        if not self.is_auto_title_candidate(session.title):
            return self._build_session_detail(session, dataset_service=None)

        updated_session = self._repository.update_title_if_current(
            session_id=session_id,
            current_title=session.title,
            title=normalized_title,
        )
        return self._build_session_detail(updated_session, dataset_service=None)

    def delete(self, session_id: str) -> SessionDeleteResponse:
        self._repository.delete(session_id)
        return SessionDeleteResponse(id=session_id, deleted=True)

    def attach_dataset(
        self, session_id: str, dataset_id: str, *, title: str | None = None
    ) -> SessionDatasetLinkResponse:
        session = self._get_session(session_id)
        if session is None:
            self._create_session(session_id, title=title)
        session = self._repository.attach_dataset(
            session_id=session_id,
            dataset_id=dataset_id,
        )
        return SessionDatasetLinkResponse(
            session_id=session_id,
            dataset_ids=[link.dataset_id for link in session.dataset_links],
        )

    def detach_dataset(
        self, session_id: str, dataset_id: str
    ) -> SessionDatasetLinkResponse:
        session = self._repository.detach_dataset(
            session_id=session_id,
            dataset_id=dataset_id,
        )
        return SessionDatasetLinkResponse(
            session_id=session_id,
            dataset_ids=[link.dataset_id for link in session.dataset_links],
        )

    def list_linked_sessions(self, dataset_id: str) -> list[tuple[str, datetime]]:
        links = self._repository.list_linked_sessions(dataset_id)
        return [
            (link.session_id, self._coerce_datetime(link.linked_at)) for link in links
        ]

    def record_analysis(
        self,
        *,
        session_id: str,
        dataset_id: str | None,
        analytics: AnalyticsPayload | None,
        workspace: WorkspacePayload | None,
        title: str | None = None,
    ) -> None:
        session = self._get_session(session_id)
        if session is None:
            self._create_session(session_id, title=title)
        self._repository.record_analysis(
            session_id=session_id,
            dataset_ids=[dataset_id] if dataset_id else [],
            analytics=self._dump_analytics(analytics),
            workspace=self._dump_workspace(workspace),
        )

    def record_message_context(
        self,
        *,
        session_id: str,
        dataset_ids: list[str],
        analytics: AnalyticsPayload | None,
        workspace: WorkspacePayload | None,
    ) -> None:
        """메시지 처리 결과로 확정된 세션 상태만 갱신합니다."""
        session = self._get_session(session_id)
        if session is None:
            self._create_session(session_id)
        self._repository.record_analysis(
            session_id=session_id,
            dataset_ids=dataset_ids,
            analytics=self._dump_analytics(analytics),
            workspace=self._dump_workspace(workspace),
        )

    def get_snapshot(
        self, session_id: str, dataset_service: "_SessionDatasetReader"
    ) -> SessionSnapshotResponse:
        session = self._repository.get_or_raise(session_id)
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
            messages=self._build_timeline_messages(
                self._message_repository.list_session_timeline(session_id)
            ),
            dataset_ids=[link.dataset_id for link in session.dataset_links],
            datasets=datasets,
            analytics=self._build_analytics(session.analytics),
            workspace=self._build_workspace(session.workspace),
        )

    def _normalize_title(self, title: str | None) -> str | None:
        if title is None:
            return None
        normalized = " ".join(title.strip().split())
        if not normalized:
            return None
        return normalized[:60]

    def _resolve_session_title(self, session_id: str, title: str | None) -> str:
        """세션 생성 시 사용할 기본 제목을 결정합니다."""
        return self._normalize_title(title) or f"Session {session_id[:8]}"

    def _get_session(self, session_id: str) -> SessionOrm | None:
        """세션을 조회하고 없으면 None을 반환합니다."""
        return self._repository.get(session_id)

    def _create_session(
        self, session_id: str, *, title: str | None = None
    ) -> SessionOrm:
        """서비스 계층에서 결정한 제목으로 세션을 생성합니다."""
        return self._repository.create(
            session_id=session_id,
            title=self._resolve_session_title(session_id, title),
        )

    def is_auto_title_candidate(self, title: str | None) -> bool:
        normalized = self._normalize_title(title)
        if normalized is None:
            return True
        return any(
            pattern.fullmatch(normalized) for pattern in self._DEFAULT_TITLE_PATTERNS
        )

    def _build_session_detail(
        self, session: SessionOrm, dataset_service: "_SessionDatasetReader | None"
    ) -> SessionDetail:
        last_dataset = self._build_last_dataset(session, dataset_service)
        return SessionDetail(
            id=session.id,
            title=session.title,
            created_at=self._coerce_datetime(session.created_at),
            updated_at=self._coerce_datetime(session.updated_at),
            preferred_dataset_id=session.preferred_dataset_id,
            message_count=self._message_repository.count_session_messages(session.id),
            dataset_count=len(session.dataset_links),
            last_dataset=last_dataset,
        )

    def hydrate_session_detail(
        self, session_id: str, dataset_service: "_SessionDatasetReader"
    ) -> SessionDetail:
        session = self._repository.get_or_raise(session_id)
        return self._build_session_detail(session, dataset_service)

    def _build_last_dataset(
        self, session: SessionOrm, dataset_service: "_SessionDatasetReader | None"
    ) -> SessionLastDataset | None:
        if dataset_service is None or not session.dataset_links:
            return None
        last_dataset_id = session.dataset_links[0].dataset_id
        try:
            dataset = dataset_service.get(last_dataset_id)
        except KeyError:
            return None
        return SessionLastDataset(id=dataset.id, filename=dataset.filename)

    def _build_message(self, message: SessionMessageOrm) -> SessionMessage:
        return SessionMessage(
            id=message.id,
            role=message.role,
            text=message.text,
            created_at=self._coerce_datetime(message.created_at),
            route=message.route,
            used_tools=message.used_tools or [],
            plan=message.plan or [],
            plan_explanation=message.plan_explanation,
        )

    def _build_user_message(self, message: UserMessageOrm) -> SessionMessage:
        """사용자 메시지 ORM을 세션 스냅샷 메시지로 변환합니다."""
        return SessionMessage(
            id=message.id,
            role="user",
            text=message.text,
            created_at=self._coerce_datetime(message.created_at),
            dataset_ids=[link.dataset_id for link in message.dataset_links],
        )

    def _build_bot_response(self, response: BotResponseOrm) -> SessionMessage:
        """봇 응답 ORM을 세션 스냅샷 메시지로 변환합니다."""
        return SessionMessage(
            id=response.id,
            role="assistant",
            text=response.text,
            created_at=self._coerce_datetime(response.created_at),
            route=response.route,
            used_tools=response.used_tools or [],
            plan=response.plan or [],
            plan_explanation=response.plan_explanation,
        )

    def _build_timeline_messages(
        self, messages: list[SessionMessageOrm | UserMessageOrm | BotResponseOrm]
    ) -> list[SessionMessage]:
        """분리 저장된 메시지를 기존 스냅샷 응답 형식의 타임라인으로 합칩니다."""
        timeline: list[SessionMessage] = []
        for message in messages:
            if isinstance(message, UserMessageOrm):
                timeline.append(self._build_user_message(message))
                continue
            if isinstance(message, BotResponseOrm):
                timeline.append(self._build_bot_response(message))
                continue
            timeline.append(self._build_message(message))
        return timeline

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

    def _dump_analytics(
        self, payload: AnalyticsPayload | None
    ) -> dict[str, object] | None:
        """분석 페이로드를 DB 저장 가능한 dict로 변환합니다."""
        if payload is None:
            return None
        return payload.model_dump(mode="json")

    def _dump_workspace(
        self, payload: WorkspacePayload | None
    ) -> dict[str, object] | None:
        """워크스페이스 페이로드를 DB 저장 가능한 dict로 변환합니다."""
        if payload is None:
            return None
        return payload.model_dump(mode="json")

    def _coerce_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)
