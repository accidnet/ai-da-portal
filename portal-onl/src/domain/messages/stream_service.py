import json
import logging
from collections.abc import Generator
from typing import Protocol, cast

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

from agents.runtimes import ChatStreamingAgent
from agents.state import AgentRoute
from domain.messages.schemas import (
    MessageStreamRequest,
    SseEvent,
)
from domain.sessions.service import SessionService
from domain.shared import AnalyticsPayload, WorkspacePayload
from infrastructure.ai.client import AiClientError
from infrastructure.db.repositories import MessageRepository

logger = logging.getLogger(__name__)
CHAT_COMPLETED_EVENT_TYPE = "chat.completed"


class _SnapshotAgent(Protocol):
    def snapshot_state(self, state: dict[str, object]) -> dict[str, object]: ...


class MessageStreamService:
    """채팅 스트리밍 응답과 세션 메시지 저장 흐름을 관리합니다."""

    def __init__(
        self,
        session_service: SessionService,
        message_repository: MessageRepository,
    ) -> None:
        self._session_service = session_service
        self._message_repository = message_repository

    async def create_streaming_response(
        self,
        *,
        stream_request: MessageStreamRequest,
        agent_runtime: ChatStreamingAgent,
    ) -> StreamingResponse:
        """사용자 메시지를 먼저 저장한 뒤 SSE 스트리밍 응답을 생성합니다."""

        session_id = stream_request.session_id.strip()

        # session id가 없을 경우 오류 발생
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="session_id is required.",
            )

        # session id가 조회되지 않을 경우 오류 발생
        try:
            self._session_service.get(session_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "유효하지 않은 session_id입니다. "
                    "새 채팅 세션을 생성한 뒤 다시 시도해 주세요."
                ),
            ) from exc

        # 사용자 입력 메세지는 바로 저장
        user_message_id = self._message_repository.record_user_message(
            session_id=session_id,
            user_message=stream_request.message,
            dataset_ids=stream_request.uploaded_dataset_ids,
        )

        # 스트리밍 시작
        return StreamingResponse(
            self._generate_stream_events(
                session_id=session_id,
                user_message_id=user_message_id,
                message=stream_request.message,
                dataset_ids=stream_request.uploaded_dataset_ids,
                agent_runtime=agent_runtime,
            ),
            media_type="text/event-stream",
            status_code=status.HTTP_202_ACCEPTED,
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    def _generate_stream_events(
        self,
        *,
        session_id: str,
        user_message_id: str | None,
        message: str,
        dataset_ids: list[str],
        agent_runtime: ChatStreamingAgent,
    ) -> Generator[str, None, None]:
        """에이전트 이벤트를 SSE로 변환하고 완료 응답을 저장합니다."""

        try:
            agent_events = agent_runtime.invoke(
                {
                    "session_id": session_id,
                    "message": message,
                    "dataset_ids": dataset_ids,
                }
            )

            while True:
                try:
                    event = next(agent_events)
                except StopIteration as exc:
                    state = cast(dict[str, object], exc.value)
                    break

                event_type = event.get("type")
                yield self._encode_sse_event(
                    SseEvent(
                        event_type=event_type if isinstance(event_type, str) else None,
                        data=event,
                    )
                )

            snapshot = self._snapshot_state(agent_runtime, state)
            self._record_chat_snapshot(
                session_id=session_id,
                user_message_id=user_message_id,
                dataset_ids=dataset_ids,
                snapshot=snapshot,
            )

            yield self._encode_sse_event(
                SseEvent(
                    event_type=CHAT_COMPLETED_EVENT_TYPE,
                    data={
                        "response": {
                            "assistant_message": snapshot["assistant_message"],
                            "used_tools": snapshot["used_tools"],
                            "plan": snapshot["plan"],
                            "plan_explanation": snapshot["plan_explanation"],
                            "analytics": (
                                snapshot["analytics"].model_dump(mode="json")
                                if isinstance(
                                    snapshot["analytics"],
                                    AnalyticsPayload,
                                )
                                else None
                            ),
                            "workspace": (
                                snapshot["workspace"].model_dump(mode="json")
                                if isinstance(
                                    snapshot["workspace"],
                                    WorkspacePayload,
                                )
                                else None
                            ),
                        },
                    },
                )
            )
        except AiClientError as exc:
            logger.exception(
                "Streaming chat request failed session_id=%s dataset_count=%s",
                session_id,
                len(dataset_ids),
            )
            yield self._encode_sse_event(
                SseEvent(
                    event_type="error",
                    data={"type": "error", "detail": str(exc)},
                )
            )

    def _record_chat_snapshot(
        self,
        *,
        session_id: str,
        user_message_id: str | None,
        dataset_ids: list[str],
        snapshot: dict[str, object],
    ) -> None:
        """저장된 사용자 메시지에 스트리밍 완료 응답을 연결합니다."""
        # 업로드/분석으로 확정된 데이터셋을 스트리밍 대화 기록에 함께 남깁니다.
        snapshot_dataset_ids = dataset_ids
        resolved_dataset_id = snapshot["resolved_dataset_id"]
        if resolved_dataset_id is not None:
            snapshot_dataset_ids = [str(resolved_dataset_id), *snapshot_dataset_ids]

        if user_message_id is not None:
            self._message_repository.record_bot_response(
                session_id=session_id,
                user_message_id=user_message_id,
                assistant_message=str(snapshot["assistant_message"]),
                route=cast(AgentRoute, snapshot["route"]),
                used_tools=cast(list[str], snapshot["used_tools"]),
                plan=cast(list[dict[str, str]], snapshot["plan"]),
                plan_explanation=cast(str | None, snapshot["plan_explanation"]),
                status=str(snapshot["status"]),
            )
        self._session_service.record_message_context(
            session_id=session_id,
            dataset_ids=snapshot_dataset_ids,
            analytics=cast(AnalyticsPayload | None, snapshot["analytics"]),
            workspace=cast(WorkspacePayload | None, snapshot["workspace"]),
        )

    def _snapshot_state(
        self, agent_runtime: _SnapshotAgent, state: dict[str, object]
    ) -> dict[str, object]:
        """에이전트 런타임 상태를 저장과 응답에 사용할 스냅샷으로 정규화합니다."""
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

    def _encode_sse_event(self, event: SseEvent) -> str:
        """SSE 이벤트 모델을 클라이언트 전송 문자열로 인코딩합니다."""
        # 이벤트 타입이 없으면 SSE 기본 이벤트명인 message로 보냅니다.
        event_type = event.event_type or "message"
        encoded = json.dumps(event.data, ensure_ascii=False)
        return f"event: {event_type}\ndata: {encoded}\n\n"
