import logging
from typing import Protocol, cast

from fastapi import UploadFile

from agents.runtimes import ChatAgent
from agents.state import AgentRoute
from application.datasets.service import DatasetApplicationService
from domain.messages.schemas import (
    ChatInteractionDataset,
    ChatRequest,
    ChatResponse,
)
from domain.shared import AnalyticsPayload, WorkspacePayload
from domain.sessions.service import SessionService
from infrastructure.db.repositories import MessageRepository


logger = logging.getLogger(__name__)


class _SnapshotAgent(Protocol):
    def snapshot_state(self, state: dict[str, object]) -> dict[str, object]: ...


class MessageService:
    """일반 채팅 요청 처리와 세션 메시지 저장을 담당합니다."""

    def __init__(
        self,
        dataset_service: DatasetApplicationService,
        session_service: SessionService,
        message_repository: MessageRepository,
    ) -> None:
        self._dataset_service = dataset_service
        self._session_service = session_service
        self._message_repository = message_repository

    def handle_chat(
        self, payload: ChatRequest, agent_runtime: ChatAgent
    ) -> ChatResponse:
        """사용자 메시지를 저장한 뒤 에이전트 응답을 생성하고 연결합니다."""
        agent_runtime = cast(ChatAgent, agent_runtime)
        logger.debug(
            "Handling chat session_id=%s dataset_ids=%s",
            payload.session_id,
            payload.dataset_ids,
        )
        self._session_service.ensure_session(payload.session_id)
        user_message_id = self._message_repository.record_user_message(
            session_id=payload.session_id,
            user_message=payload.message,
            dataset_ids=payload.dataset_ids,
        )
        state = agent_runtime.invoke(
            {
                "session_id": payload.session_id,
                "message": payload.message,
                "dataset_ids": payload.dataset_ids,
            }
        )
        snapshot = self.snapshot_state(agent_runtime, state)
        logger.debug(
            "Agent graph completed session_id=%s route=%s tools=%s has_analytics=%s",
            payload.session_id,
            snapshot["route"],
            snapshot["used_tools"],
            snapshot["analytics"] is not None,
        )

        self.record_chat_snapshot(
            payload=payload,
            user_message_id=user_message_id,
            snapshot=snapshot,
        )

        return ChatResponse(
            session_id=payload.session_id,
            assistant_message=snapshot["assistant_message"],
            route=snapshot["route"],
            used_tools=snapshot["used_tools"],
            plan=snapshot["plan"],
            plan_explanation=snapshot["plan_explanation"],
            status=snapshot["status"],
            analytics=snapshot["analytics"],
            workspace=snapshot["workspace"],
        )

    async def prepare_chat_request(
        self,
        *,
        session_id: str,
        message: str,
        dataset_ids: list[str],
        file: UploadFile | None,
    ) -> tuple[ChatRequest, ChatInteractionDataset | None]:
        """업로드 파일을 데이터셋으로 변환하고 채팅 요청 입력을 정규화합니다."""
        resolved_dataset_ids = list(dataset_ids)
        interaction_dataset: ChatInteractionDataset | None = None

        if file is not None:
            detail = await self._dataset_service.upload(file)
            self._session_service.attach_dataset(
                session_id,
                detail.id,
                title=detail.filename,
            )
            preview = self._dataset_service.get_preview(detail.id)
            profile = self._dataset_service.get_profile(detail.id)
            interaction_dataset = ChatInteractionDataset(
                detail=detail,
                preview=preview,
                profile=profile,
            )
            resolved_dataset_ids = [detail.id, *resolved_dataset_ids]

        return (
            ChatRequest(
                session_id=session_id,
                message=message,
                dataset_ids=resolved_dataset_ids,
            ),
            interaction_dataset,
        )

    def snapshot_state(
        self, agent_runtime: _SnapshotAgent, state: dict[str, object]
    ) -> dict[str, object]:
        """에이전트 상태를 외부 응답에 사용할 스냅샷으로 변환합니다."""
        return self._snapshot_state(agent_runtime, state)

    def record_chat_snapshot(
        self,
        *,
        payload: ChatRequest,
        user_message_id: str | None,
        snapshot: dict[str, object],
    ) -> None:
        """저장된 사용자 메시지에 일반 채팅 응답을 연결합니다."""
        # 업로드/분석으로 확정된 데이터셋을 대화 기록에 함께 남깁니다.
        snapshot_dataset_ids = payload.dataset_ids
        resolved_dataset_id = snapshot["resolved_dataset_id"]
        if resolved_dataset_id is not None:
            snapshot_dataset_ids = [resolved_dataset_id, *snapshot_dataset_ids]

        if user_message_id is not None:
            self._message_repository.record_bot_response(
                session_id=payload.session_id,
                user_message_id=user_message_id,
                assistant_message=str(snapshot["assistant_message"]),
                route=cast(AgentRoute, snapshot["route"]),
                used_tools=cast(list[str], snapshot["used_tools"]),
                plan=cast(list[dict[str, str]], snapshot["plan"]),
                plan_explanation=cast(str | None, snapshot["plan_explanation"]),
                status=str(snapshot["status"]),
            )
        self._session_service.record_message_context(
            session_id=payload.session_id,
            dataset_ids=snapshot_dataset_ids,
            analytics=cast(AnalyticsPayload | None, snapshot["analytics"]),
            workspace=cast(WorkspacePayload | None, snapshot["workspace"]),
        )

    def _snapshot_state(
        self, agent_runtime: _SnapshotAgent, state: dict[str, object]
    ) -> dict[str, object]:
        """에이전트 런타임별 스냅샷 함수가 없을 때 기본 스냅샷을 구성합니다."""
        snapshot_state = getattr(agent_runtime, "snapshot_state", None)
        if callable(snapshot_state):
            return cast(dict[str, object], snapshot_state(state))

        route = cast(AgentRoute, state.get("route", "conversation"))
        assistant_message = str(state.get("assistant_message", "")).strip()
        analytics = state.get("analytics")
        workspace = state.get("workspace")
        if not assistant_message and (
            isinstance(analytics, AnalyticsPayload) or workspace is not None
        ):
            assistant_message = (
                "백엔드 분석은 완료됐어요. 요약과 시각화 결과를 확인해 주세요."
            )
        return {
            "route": route,
            "assistant_message": assistant_message,
            "used_tools": [
                tool for tool in state.get("used_tools", []) if isinstance(tool, str)
            ],
            "plan": [step for step in state.get("plan", []) if isinstance(step, dict)],
            "plan_explanation": (
                state.get("plan_explanation")
                if isinstance(state.get("plan_explanation"), str)
                else None
            ),
            "analytics": analytics if isinstance(analytics, AnalyticsPayload) else None,
            "workspace": workspace,
            "resolved_dataset_id": state.get("resolved_dataset_id"),
            "analysis_type": state.get("analysis_type"),
            "status": state.get(
                "status", "completed" if assistant_message else "queued"
            ),
        }
