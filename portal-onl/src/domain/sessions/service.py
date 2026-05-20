from datetime import UTC, datetime
import re
from typing import Protocol
from uuid import uuid4

from pydantic import ValidationError

from features.datasets.api.schemas import (
    DatasetInfo,
    DatasetPreviewResponse,
    DatasetProfileResponse,
)
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
from features.tools.charts.dto import AnalyticsPayload, ChartPayload
from infrastructure.db.models import AgentTimelineItemOrm, SessionOrm, UserMessageOrm
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

    def create(self, payload: SessionCreateRequest) -> SessionDetail:
        session_id = str(uuid4())
        session = self._repository.create(
            session_id=session_id,
            title=self._normalize_title(payload.title) or "New analysis session",
            workspace_id=self._normalize_workspace_id(payload.workspace_id),
        )
        return self._build_session_detail(session, dataset_service=None)

    def ensure_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        workspace_id: str | None = None,
    ) -> SessionDetail:
        session = self._get_session(session_id)
        if session is None:
            session = self._create_session(
                session_id,
                title=title,
                workspace_id=workspace_id,
            )
        return self._build_session_detail(session, dataset_service=None)

    def list_sessions(
        self,
        dataset_service: "_SessionDatasetReader",
        *,
        workspace_id: str | None = None,
    ) -> list[SessionSummary]:
        sessions = self._repository.list_sessions(
            workspace_id=self._normalize_workspace_id(workspace_id)
        )
        return [
            self._build_session_detail(session, dataset_service) for session in sessions
        ]

    def get(self, session_id: str) -> SessionDetail:
        session = self._repository.get_or_raise(session_id)
        return self._build_session_detail(session, dataset_service=None)

    def get_dataset_ids(self, session_id: str) -> list[str]:
        """세션에 사용자가 명시적으로 연결한 데이터셋 ID를 반환합니다."""
        return self._repository.list_session_dataset_ids(session_id)

    def update(self, session_id: str, payload: SessionUpdateRequest) -> SessionDetail:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("At least one of 'title' must be provided.")

        normalized_title = self._normalize_title(payload.title)
        if normalized_title is None:
            raise ValueError("Session title must not be empty.")

        updated_session = self._repository.update_session(
            session_id=session_id,
            title=normalized_title,
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
        """세션과 데이터셋의 직접 연결을 저장합니다."""
        session = self._get_session(session_id)
        if session is None:
            self._create_session(session_id, title=title)
        dataset_ids = self._repository.attach_dataset(
            session_id=session_id,
            dataset_id=dataset_id,
        )
        return SessionDatasetLinkResponse(session_id=session_id, dataset_ids=dataset_ids)

    def detach_dataset(
        self, session_id: str, dataset_id: str
    ) -> SessionDatasetLinkResponse:
        """세션과 데이터셋의 직접 연결을 제거합니다."""
        dataset_ids = self._repository.detach_dataset(
            session_id=session_id,
            dataset_id=dataset_id,
        )
        return SessionDatasetLinkResponse(session_id=session_id, dataset_ids=dataset_ids)

    def list_linked_sessions(self, dataset_id: str) -> list[tuple[str, datetime]]:
        return [
            (session_id, self._coerce_datetime(linked_at))
            for session_id, linked_at in self._repository.list_linked_sessions(
                dataset_id
            )
        ]

    def record_analysis(
        self,
        *,
        session_id: str,
        dataset_id: str | None,
        title: str | None = None,
        **_: object,
    ) -> None:
        """레거시 분석 캐시 저장 대신 세션 존재와 갱신 시각만 보장합니다."""
        session = self._get_session(session_id)
        if session is None:
            self._create_session(session_id, title=title)
            return
        self._repository.touch(session_id)

    def record_message_context(
        self,
        *,
        session_id: str,
        **_: object,
    ) -> None:
        """메시지 처리 후 세션 갱신 시각만 업데이트합니다."""
        session = self._get_session(session_id)
        if session is None:
            self._create_session(session_id)
            return
        self._repository.touch(session_id)

    def get_snapshot(
        self, session_id: str, dataset_service: "_SessionDatasetReader"
    ) -> SessionSnapshotResponse:
        session = self._repository.get_or_raise(session_id)
        dataset_ids = self.get_dataset_ids(session_id)
        datasets: list[SessionSnapshotDataset] = []
        for dataset_id in dataset_ids:
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

        timeline_messages = self._message_repository.list_session_timeline(session_id)

        return SessionSnapshotResponse(
            session=self._build_session_detail(session, dataset_service),
            messages=self._build_timeline_messages(timeline_messages),
            dataset_ids=dataset_ids,
            datasets=datasets,
            analytics_payload=self._build_snapshot_analytics_payload(
                timeline_messages
            ),
        )

    def _normalize_title(self, title: str | None) -> str | None:
        if title is None:
            return None
        normalized = " ".join(title.strip().split())
        if not normalized:
            return None
        return normalized[:60]

    def _normalize_workspace_id(self, workspace_id: str | None) -> str | None:
        """워크스페이스 연결에 사용할 ID를 정규화합니다."""
        if workspace_id is None:
            return None
        normalized = workspace_id.strip()
        return normalized or None

    def _resolve_session_title(self, session_id: str, title: str | None) -> str:
        """세션 생성 시 사용할 기본 제목을 결정합니다."""
        return self._normalize_title(title) or f"Session {session_id[:8]}"

    def _get_session(self, session_id: str) -> SessionOrm | None:
        """세션을 조회하고 없으면 None을 반환합니다."""
        return self._repository.get(session_id)

    def _create_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        workspace_id: str | None = None,
    ) -> SessionOrm:
        """서비스 계층에서 결정한 제목으로 세션을 생성합니다."""
        return self._repository.create(
            session_id=session_id,
            title=self._resolve_session_title(session_id, title),
            workspace_id=self._normalize_workspace_id(workspace_id),
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
        dataset_ids = self.get_dataset_ids(session.id)
        last_dataset = self._build_last_dataset(dataset_ids, dataset_service)
        return SessionDetail(
            id=session.id,
            workspace_id=session.workspace_id,
            title=session.title,
            created_at=self._coerce_datetime(session.created_at),
            updated_at=self._coerce_datetime(session.updated_at),
            message_count=self._message_repository.count_session_messages(session.id),
            dataset_count=len(dataset_ids),
            last_dataset=last_dataset,
        )

    def hydrate_session_detail(
        self, session_id: str, dataset_service: "_SessionDatasetReader"
    ) -> SessionDetail:
        session = self._repository.get_or_raise(session_id)
        return self._build_session_detail(session, dataset_service)

    def _build_last_dataset(
        self,
        dataset_ids: list[str],
        dataset_service: "_SessionDatasetReader | None",
    ) -> SessionLastDataset | None:
        if dataset_service is None or not dataset_ids:
            return None
        try:
            dataset = dataset_service.get(dataset_ids[0])
        except KeyError:
            return None
        return SessionLastDataset(id=dataset.id, filename=dataset.filename)

    def _build_user_message(self, message: UserMessageOrm) -> SessionMessage:
        """사용자 메시지 ORM을 세션 스냅샷 메시지로 변환합니다."""
        return SessionMessage(
            id=message.id,
            role="user",
            text=message.text,
            created_at=self._coerce_datetime(message.created_at),
            dataset_ids=[link.dataset_id for link in message.dataset_links],
        )

    def _build_timeline_item(self, item: AgentTimelineItemOrm) -> SessionMessage | None:
        """프론트 노출 timeline item을 세션 메시지로 변환합니다."""
        payload = item.stream_payload or {}
        role = payload.get("role")
        text = payload.get("text")
        if role not in {"user", "assistant"} or not isinstance(text, str):
            return None
        return SessionMessage(
            id=item.id,
            role=role,
            text=text,
            created_at=self._coerce_datetime(item.created_at),
            dataset_ids=[
                dataset_id
                for dataset_id in payload.get("dataset_ids", [])
                if isinstance(dataset_id, str)
            ],
            used_tools=[
                tool for tool in payload.get("used_tools", []) if isinstance(tool, str)
            ],
            plan=[
                step for step in payload.get("plan", []) if isinstance(step, dict)
            ],
            plan_explanation=(
                payload.get("plan_explanation")
                if isinstance(payload.get("plan_explanation"), str)
                else None
            ),
            sub_messages=[
                sub_message
                for sub_message in payload.get("sub_messages", [])
                if isinstance(sub_message, dict)
            ],
        )

    def _build_timeline_messages(
        self, messages: list[UserMessageOrm | AgentTimelineItemOrm]
    ) -> list[SessionMessage]:
        """사용자 메시지와 agent timeline을 기존 스냅샷 메시지 형식으로 변환합니다."""
        timeline: list[SessionMessage] = []
        for message in messages:
            if isinstance(message, UserMessageOrm):
                timeline.append(self._build_user_message(message))
                continue
            timeline_item = self._build_timeline_item(message)
            if timeline_item is not None:
                timeline.append(timeline_item)
        return timeline

    def _build_snapshot_analytics_payload(
        self, messages: list[UserMessageOrm | AgentTimelineItemOrm]
    ) -> AnalyticsPayload | None:
        """assistant timeline에 저장된 chart payload를 세션 복원용 analytics payload로 모읍니다."""
        charts: list[ChartPayload] = []
        seen_chart_signatures: set[str] = set()
        for message in messages:
            if not isinstance(message, AgentTimelineItemOrm):
                continue
            payload = message.stream_payload or {}
            for raw_chart in payload.get("charts", []):
                if not isinstance(raw_chart, dict):
                    continue
                try:
                    chart = ChartPayload.model_validate(raw_chart)
                except ValidationError:
                    continue
                signature = chart.model_dump_json()
                if signature in seen_chart_signatures:
                    continue
                seen_chart_signatures.add(signature)
                charts.append(chart)

        if not charts:
            return None
        return AnalyticsPayload(charts=charts)

    def _coerce_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)
