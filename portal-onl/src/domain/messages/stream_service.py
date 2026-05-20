import json
import logging
from collections.abc import Generator
from typing import Protocol, cast

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

from features.agents.runtimes import ChatStreamingAgent
from features.agents.state import AgentInvokeOutput
from features.workspaces.application.local_storage import WorkspaceLocalStorage
from core.sse import SseEvent
from domain.messages.schemas import (
    MessageStreamRequest,
)
from domain.sessions.service import SessionService
from infrastructure.ai.client import AiClientError
from infrastructure.db.repositories import MessageRepository
from shared.integrations.ai.contracts import EasyInputMessage, InputItemList

logger = logging.getLogger(__name__)
CHAT_COMPLETED_EVENT_TYPE = "chat.completed"


class _SnapshotAgent(Protocol):
    def snapshot_state(self, state: dict[str, object]) -> dict[str, object]: ...
    def snapshot_output(self, output: AgentInvokeOutput) -> dict[str, object]: ...


class MessageStreamService:
    """채팅 스트리밍 응답과 세션 메시지 저장 흐름을 관리합니다."""

    def __init__(
        self,
        session_service: SessionService,
        message_repository: MessageRepository,
        workspace_local_storage: WorkspaceLocalStorage,
    ) -> None:
        self._session_service = session_service
        self._message_repository = message_repository
        self._workspace_local_storage = workspace_local_storage

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
            session = self._session_service.get(session_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "유효하지 않은 session_id입니다. "
                    "새 채팅 세션을 생성한 뒤 다시 시도해 주세요."
                ),
            ) from exc
        workspace_id = self._normalize_workspace_id(stream_request.workspace_id)
        if workspace_id is not None and session.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="session_id does not belong to the requested workspace_id.",
            )
        workspace_local_path = (
            str(self._workspace_local_storage.ensure_workspace(workspace_id))
            if workspace_id is not None
            else None
        )

        # 사용자 입력 메세지는 바로 저장
        user_message_id = self._message_repository.record_user_message(
            session_id=session_id,
            user_message=stream_request.message,
            dataset_ids=stream_request.dataset_ids,
        )

        # 스트리밍 시작
        return StreamingResponse(
            self._generate_stream_events(
                session_id=session_id,
                user_message_id=user_message_id,
                workspace_id=workspace_id,
                workspace_local_path=workspace_local_path,
                message=stream_request.message,
                dataset_ids=stream_request.dataset_ids,
                agent_runtime=agent_runtime,
            ),
            media_type="text/event-stream",
            status_code=status.HTTP_202_ACCEPTED,
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    def _normalize_workspace_id(self, workspace_id: str | None) -> str | None:
        """채팅 요청의 선택적 워크스페이스 ID를 정규화합니다."""
        if workspace_id is None:
            return None
        normalized = workspace_id.strip()
        return normalized or None

    def _generate_stream_events(
        self,
        *,
        session_id: str,
        user_message_id: str | None,
        workspace_id: str | None,
        workspace_local_path: str | None,
        message: str,
        dataset_ids: list[str],
        agent_runtime: ChatStreamingAgent,
    ) -> Generator[str, None, None]:
        """에이전트 이벤트를 SSE로 변환하고 완료 응답을 저장합니다."""

        try:
            streamed_text_parts: list[str] = []
            sub_messages: dict[str, dict[str, object]] = {}
            charts: list[dict[str, object]] = []
            should_separate_next_text = False
            agent_run_id = (
                self._message_repository.create_agent_run(
                    session_id=session_id,
                    user_message_id=user_message_id,
                )
                if user_message_id is not None
                else None
            )
            input_items = (
                self._message_repository.list_session_conversation_input_items(
                    session_id
                )
            )
            logger.debug(
                "Loaded session conversation input items session_id=%s count=%s",
                session_id,
                len(input_items),
            )
            agent_events = agent_runtime.invoke(
                {
                    "session_id": session_id,
                    "workspace_id": workspace_id,
                    "workspace_local_path": workspace_local_path,
                    "message": message,
                    "dataset_ids": dataset_ids,
                    "input_items": input_items,
                }
            )

            while True:
                try:
                    event = next(agent_events)
                except StopIteration as exc:
                    output, _agent_results = self._unpack_agent_invoke_result(
                        exc.value
                    )
                    break

                sse_event = self._coerce_sse_event(event)
                should_separate_next_text = self._record_stream_event(
                    event=sse_event,
                    streamed_text_parts=streamed_text_parts,
                    sub_messages=sub_messages,
                    charts=charts,
                    should_separate_next_text=should_separate_next_text,
                )
                yield self._encode_sse_event(sse_event)

            snapshot = self._snapshot_output(agent_runtime, output)
            streamed_text = "".join(streamed_text_parts).strip()
            if streamed_text and not str(snapshot["assistant_message"]).strip():
                snapshot["assistant_message"] = streamed_text
            self._record_chat_snapshot(
                session_id=session_id,
                user_message_id=user_message_id,
                agent_run_id=agent_run_id,
                input_items=self._extract_input_items(output),
                snapshot=snapshot,
                sub_messages=sub_messages,
                charts=charts,
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
        finally:
            # 스트리밍 정상 종료, 오류, 클라이언트 연결 종료 모두 요청 단위 메모리를 정리합니다.
            agent_runtime.cleanup_runtime_resources()
            logger.debug(
                "Cleaned agent runtime resources session_id=%s",
                session_id,
            )

    def _record_chat_snapshot(
        self,
        *,
        session_id: str,
        user_message_id: str | None,
        agent_run_id: str | None,
        input_items: list[dict[str, object]],
        snapshot: dict[str, object],
        sub_messages: dict[str, dict[str, object]],
        charts: list[dict[str, object]],
    ) -> None:
        """완료된 assistant 응답을 agent timeline에 저장합니다."""
        assistant_message = str(snapshot["assistant_message"]).strip()
        if user_message_id is not None:
            self._message_repository.record_agent_input_items(
                session_id=session_id,
                user_message_id=user_message_id,
                agent_run_id=agent_run_id,
                input_items=input_items,
            )
            self._message_repository.record_agent_response(
                session_id=session_id,
                user_message_id=user_message_id,
                agent_run_id=agent_run_id,
                assistant_message=assistant_message,
                input_item=(
                    None
                    if input_items
                    else self._build_assistant_input_item(assistant_message)
                ),
                stream_payload=self._build_assistant_stream_payload(
                    assistant_message=assistant_message,
                    snapshot=snapshot,
                    sub_messages=sub_messages,
                    charts=charts,
                ),
                is_input_reusable=not input_items and bool(assistant_message),
            )
        self._session_service.record_message_context(session_id=session_id)

    def _build_assistant_stream_payload(
        self,
        *,
        assistant_message: str,
        snapshot: dict[str, object],
        sub_messages: dict[str, dict[str, object]],
        charts: list[dict[str, object]],
    ) -> dict[str, object]:
        """세션 복원에 필요한 assistant 결과 payload를 저장 형태로 변환합니다."""
        return {
            "role": "assistant",
            "text": assistant_message,
            "used_tools": snapshot.get("used_tools") or [],
            "plan": snapshot.get("plan") or [],
            "plan_explanation": snapshot.get("plan_explanation"),
            "sub_messages": list(sub_messages.values()),
            "charts": charts,
        }

    def _build_assistant_input_item(
        self, assistant_message: str
    ) -> dict[str, object] | None:
        """완료된 assistant 메시지를 다음 LLM input 재사용 payload로 변환합니다."""
        if not assistant_message:
            return None
        return InputItemList(
            items=(
                EasyInputMessage(
                    role="assistant",
                    content=assistant_message,
                    phase="final_answer",
                ),
            )
        ).to_payload()[0]

    def _unpack_agent_invoke_result(
        self, invoke_result: object
    ) -> tuple[AgentInvokeOutput, dict[str, object]]:
        """에이전트 실행 종료값에서 출력과 부가 결과를 분리합니다."""
        # 이전 반환 형태인 state 단독 값도 허용해 스트리밍 처리 흐름을 유지합니다.
        if isinstance(invoke_result, tuple) and len(invoke_result) == 2:
            output, results = invoke_result
            return cast(AgentInvokeOutput, output), cast(dict[str, object], results)

        return cast(AgentInvokeOutput, invoke_result), {}

    def _extract_input_items(self, output: AgentInvokeOutput) -> list[dict[str, object]]:
        """agent output에서 timeline에 저장할 input item 목록을 정규화합니다."""
        input_items = output.get("input_items", [])
        if not isinstance(input_items, list):
            return []
        return [item for item in input_items if isinstance(item, dict)]

    def _record_stream_event(
        self,
        *,
        event: SseEvent,
        streamed_text_parts: list[str],
        sub_messages: dict[str, dict[str, object]],
        charts: list[dict[str, object]],
        should_separate_next_text: bool,
    ) -> bool:
        """프론트로 내보낸 SSE 이벤트를 히스토리 저장용 메시지 조각으로 누적합니다."""
        event_type = event.event_type or "message"
        data = event.data

        if event_type == "agent.iteration.start":
            iteration = data.get("iteration")
            sub_message_id = f"agent.iteration:{iteration}"
            self._upsert_sub_message(
                sub_messages,
                sub_message_id=sub_message_id,
                event_type=event_type,
                text="",
                is_streaming=True,
            )
            return bool(streamed_text_parts)

        if event_type in {"response.output_text.delta", "message.delta"}:
            delta = data.get("delta")
            if isinstance(delta, str):
                if should_separate_next_text and streamed_text_parts:
                    streamed_text_parts.append("\n\n")
                streamed_text_parts.append(delta)
            return False

        if event_type == "agent.iteration.done":
            iteration = data.get("iteration")
            sub_message_id = f"agent.iteration:{iteration}"
            existing_text = str(sub_messages.get(sub_message_id, {}).get("text") or "")
            self._upsert_sub_message(
                sub_messages,
                sub_message_id=sub_message_id,
                event_type=event_type,
                text=existing_text or "Step completed.",
                is_streaming=False,
            )
            return should_separate_next_text

        if event_type == "agent.iteration.plan":
            self._upsert_sub_message(
                sub_messages,
                sub_message_id="agent.plan",
                event_type=event_type,
                text=self._format_plan_text(data),
                is_streaming=False,
            )
            return should_separate_next_text

        if event_type == "agent.iteration.chart":
            chart = data.get("chart")
            title = chart.get("title") if isinstance(chart, dict) else None
            if isinstance(chart, dict):
                self._append_chart_payload(charts, chart)
            self._upsert_sub_message(
                sub_messages,
                sub_message_id=f"agent.chart:{title or len(sub_messages)}",
                event_type=event_type,
                text=self._format_chart_text(data),
                is_streaming=False,
            )
            return should_separate_next_text

        if event_type == "agent.function_call.output":
            name = data.get("name")
            self._upsert_sub_message(
                sub_messages,
                sub_message_id=f"agent.tool:{name or len(sub_messages)}",
                event_type=event_type,
                text=str(data.get("text") or ""),
                is_streaming=False,
            )
            return should_separate_next_text

        return should_separate_next_text

    def _append_chart_payload(
        self, charts: list[dict[str, object]], chart: dict[str, object]
    ) -> None:
        """세션 복원에 사용할 chart payload를 중복 없이 누적합니다."""
        if chart in charts:
            return
        charts.append(chart)

    def _upsert_sub_message(
        self,
        sub_messages: dict[str, dict[str, object]],
        *,
        sub_message_id: str,
        event_type: str,
        text: str,
        is_streaming: bool,
    ) -> None:
        """같은 step/tool 이벤트는 덮어써 최신 상태만 저장합니다."""
        sub_messages[sub_message_id] = {
            "id": sub_message_id,
            "type": event_type,
            "text": text,
            "is_streaming": is_streaming,
        }

    def _format_plan_text(self, data: dict[str, object]) -> str:
        """계획 SSE payload를 히스토리에 표시할 짧은 Markdown으로 변환합니다."""
        plan_data = data.get("data")
        if not isinstance(plan_data, dict):
            return ""
        explanation = plan_data.get("explanation")
        plan = plan_data.get("plan")
        lines: list[str] = []
        if isinstance(explanation, str) and explanation.strip():
            lines.append(explanation.strip())
        if isinstance(plan, list):
            for item in plan:
                if not isinstance(item, dict):
                    continue
                step = item.get("step")
                status = item.get("status")
                if isinstance(step, str):
                    lines.append(f"- [{status or 'pending'}] {step}")
        return "\n".join(lines)

    def _format_chart_text(self, data: dict[str, object]) -> str:
        """차트 SSE payload를 히스토리에 표시할 짧은 Markdown으로 변환합니다."""
        chart = data.get("chart")
        if not isinstance(chart, dict):
            return "Chart payload generated."
        title = chart.get("title")
        chart_type = chart.get("type")
        return f"{title or 'Chart'} ({chart_type or 'unknown'}) generated."

    def _snapshot_output(
        self, agent_runtime: _SnapshotAgent, output: AgentInvokeOutput
    ) -> dict[str, object]:
        """에이전트 런타임 출력을 저장과 응답에 사용할 스냅샷으로 정규화합니다."""
        snapshot_output = getattr(agent_runtime, "snapshot_output", None)
        if callable(snapshot_output):
            return cast(dict[str, object], snapshot_output(output))

        snapshot_state = getattr(agent_runtime, "snapshot_state", None)
        if callable(snapshot_state):
            return cast(
                dict[str, object],
                snapshot_state(cast(dict[str, object], output)),
            )

        assistant_message = str(output.get("assistant_message", "")).strip()
        return {
            "assistant_message": assistant_message,
            "used_tools": [
                tool for tool in output.get("used_tools", []) if isinstance(tool, str)
            ],
            "plan": [
                step for step in output.get("plan", []) if isinstance(step, dict)
            ],
            "plan_explanation": (
                output.get("plan_explanation")
                if isinstance(output.get("plan_explanation"), str)
                else None
            ),
            "resolved_dataset_id": output.get("resolved_dataset_id"),
            "analysis_type": output.get("analysis_type"),
        }

    def _encode_sse_event(self, event: SseEvent) -> str:
        """SSE 이벤트 모델을 클라이언트 전송 문자열로 인코딩합니다."""
        # 이벤트 타입이 없으면 SSE 기본 이벤트명인 message로 보냅니다.
        event_type = event.event_type or "message"
        encoded = json.dumps(event.data, ensure_ascii=False)
        return f"event: {event_type}\ndata: {encoded}\n\n"

    def _coerce_sse_event(self, event: dict[str, object] | SseEvent) -> SseEvent:
        """에이전트 이벤트를 SSE 이벤트 모델로 정규화합니다."""
        if isinstance(event, SseEvent):
            return event

        event_type = event.get("type")
        return SseEvent(
            event_type=event_type if isinstance(event_type, str) else None,
            data=event,
        )
