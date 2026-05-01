import json
import logging
import re
from collections.abc import Generator, Iterable
from typing import Protocol, cast

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from agents.runtimes import ChatStreamingAgent
from agents.state import AgentRoute
from domain.datasets.service import DatasetService
from domain.messages.schemas import (
    ChatInteractionDataset,
    ChatRequest,
    ChatResponse,
    MessageStreamRequest,
)
from domain.sessions.service import SessionService
from domain.shared import AnalyticsPayload, WorkspacePayload
from infrastructure.ai.client import AiClient, AiClientError
from infrastructure.ai.streaming_events import RESPONSE_STREAMING_EVENTS

logger = logging.getLogger(__name__)


class _SnapshotAgent(Protocol):
    def snapshot_state(self, state: dict[str, object]) -> dict[str, object]: ...


class MessageStreamService:
    def __init__(
        self,
        llm_client: AiClient,
        dataset_service: DatasetService,
        session_service: SessionService,
    ) -> None:
        self._llm_client = llm_client
        self._dataset_service = dataset_service
        self._session_service = session_service

    async def create_streaming_response(
        self,
        *,
        stream_request: MessageStreamRequest,
        files: list[UploadFile],
        agent_runtime: ChatStreamingAgent,
    ) -> StreamingResponse:
        try:
            payload, interaction_datasets = await self._prepare_stream_request(
                stream_request=stream_request,
                files=files,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        def event_stream() -> Generator[str, None, None]:
            try:
                for interaction_dataset in interaction_datasets:
                    yield self._encode_sse_event(
                        {
                            "type": "dataset.ready",
                            "dataset": interaction_dataset.model_dump(mode="json"),
                        }
                    )

                for event in self._stream_chat(
                    payload=payload,
                    agent_runtime=agent_runtime,
                ):
                    yield self._encode_sse_event(event)
            except AiClientError as exc:
                logger.exception(
                    "Streaming chat request failed session_id=%s dataset_count=%s",
                    payload.session_id,
                    len(payload.dataset_ids),
                )
                yield self._encode_sse_event({"type": "error", "detail": str(exc)})

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            status_code=status.HTTP_202_ACCEPTED,
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    def _stream_chat(
        self, payload: ChatRequest, agent_runtime: ChatStreamingAgent
    ) -> Generator[dict[str, object], None, None]:
        session_title, session_dataset_ids = self._resolve_chat_context(payload)
        logger.debug(
            "Streaming chat session_id=%s dataset_ids=%s session_dataset_ids=%s",
            payload.session_id,
            payload.dataset_ids,
            session_dataset_ids,
        )

        state = yield from agent_runtime.invoke(
            {
                "session_id": payload.session_id,
                "message": payload.message,
                "dataset_ids": payload.dataset_ids,
                "session_dataset_ids": session_dataset_ids,
            }
        )

        snapshot = self._snapshot_state(agent_runtime, state)
        self._record_chat_snapshot(
            payload=payload,
            snapshot=snapshot,
            session_dataset_ids=session_dataset_ids,
        )

        yield {
            "type": RESPONSE_STREAMING_EVENTS.response.completed,
            "response": ChatResponse(
                session_id=payload.session_id,
                session_title=session_title,
                assistant_message=snapshot["assistant_message"],
                route=snapshot["route"],
                used_tools=snapshot["used_tools"],
                plan=snapshot["plan"],
                plan_explanation=snapshot["plan_explanation"],
                status=snapshot["status"],
                analytics=snapshot["analytics"],
                workspace=snapshot["workspace"],
            ).model_dump(mode="json"),
        }

    async def _prepare_stream_request(
        self, *, stream_request: MessageStreamRequest, files: list[UploadFile]
    ) -> tuple[ChatRequest, list[ChatInteractionDataset]]:
        #  session_id가 없을 경우 오류 발생
        session_id = stream_request.session_id.strip()
        if not session_id:
            raise ValueError("session_id is required.")
        if files:
            raise ValueError("Upload datasets before starting a chat stream.")

        # 업로드 API에서 받은 dataset id의 빈 값과 중복을 제거합니다.
        uploaded_dataset_ids = self._filter_dataset_ids(
            stream_request.uploaded_dataset_ids
        )

        interaction_datasets: list[ChatInteractionDataset] = []

        return (
            ChatRequest(
                session_id=session_id,
                message=stream_request.message,
                dataset_ids=uploaded_dataset_ids,
            ),
            interaction_datasets,
        )

    def _resolve_chat_context(self, payload: ChatRequest) -> tuple[str, list[str]]:
        # 채팅 실행 전 세션 제목과 세션 데이터셋을 스트리밍 클래스 내부에서 확정합니다.
        session = self._session_service.ensure_session(payload.session_id)
        session_title = self._resolve_session_title(
            session_id=payload.session_id,
            current_title=session.title,
            user_message=payload.message,
        )
        session_dataset_ids = self._session_service.get_dataset_ids(payload.session_id)
        return session_title, session_dataset_ids

    def _record_chat_snapshot(
        self,
        *,
        payload: ChatRequest,
        snapshot: dict[str, object],
        session_dataset_ids: list[str],
    ) -> None:
        # 업로드/분석으로 확정된 데이터셋을 스트리밍 대화 기록에 함께 남깁니다.
        snapshot_dataset_ids = payload.dataset_ids or session_dataset_ids
        resolved_dataset_id = snapshot["resolved_dataset_id"]
        if resolved_dataset_id is not None:
            snapshot_dataset_ids = [str(resolved_dataset_id), *snapshot_dataset_ids]

        self._session_service.record_chat(
            session_id=payload.session_id,
            user_message=payload.message,
            assistant_message=str(snapshot["assistant_message"]),
            route=cast(AgentRoute, snapshot["route"]),
            used_tools=cast(list[str], snapshot["used_tools"]),
            plan=cast(list[dict[str, str]], snapshot["plan"]),
            plan_explanation=cast(str | None, snapshot["plan_explanation"]),
            dataset_ids=snapshot_dataset_ids,
            analytics=cast(AnalyticsPayload | None, snapshot["analytics"]),
            workspace=cast(WorkspacePayload | None, snapshot["workspace"]),
        )

    def _resolve_session_title(
        self,
        *,
        session_id: str,
        current_title: str,
        user_message: str,
    ) -> str:
        if not self._session_service.is_auto_title_candidate(current_title):
            return current_title

        generated_title = self._generate_session_title(user_message)
        return self._session_service.update_title_if_default(
            session_id=session_id,
            title=generated_title,
        ).title

    def _snapshot_state(
        self, agent_runtime: _SnapshotAgent, state: dict[str, object]
    ) -> dict[str, object]:
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

    def _generate_session_title(self, user_message: str) -> str:
        try:
            generated = self._llm_client.generate(
                system=(
                    "당신은 데이터 분석 대화의 세션 제목 생성기입니다. "
                    "사용자 첫 질문을 12~30자 안팎의 매우 짧은 한국어 제목 1개로만 요약하세요. "
                    "따옴표, 마침표, 번호, 설명 문장은 포함하지 마세요."
                ),
                user_message=f"첫 사용자 질문:\n{user_message}",
            )
            sanitized = self._sanitize_session_title(
                self._resolve_generated_text(generated)
            )
            if sanitized:
                return sanitized
        except AiClientError as exc:
            logger.info(
                "Session title generation failed; using fallback detail=%s", exc
            )

        return self._fallback_session_title(user_message)

    def _resolve_generated_text(self, generated: object) -> str:
        if isinstance(generated, str):
            return generated

        final_text: str | None = None
        deltas: list[str] = []
        close = getattr(generated, "close", None)

        try:
            for event in cast(Iterable[object], generated):
                payload = self._coerce_optional_dict(event)
                if payload is None:
                    continue

                event_type = payload.get("type")
                if (
                    event_type == RESPONSE_STREAMING_EVENTS.response.output_text.delta
                    or event_type == RESPONSE_STREAMING_EVENTS.message.delta
                ):
                    delta = payload.get("delta") or payload.get("text")
                    if isinstance(delta, str) and delta:
                        deltas.append(delta)
                    continue

                if (
                    event_type == RESPONSE_STREAMING_EVENTS.response.output_text.done
                    or event_type == RESPONSE_STREAMING_EVENTS.message.completed
                ):
                    text = payload.get("text") or payload.get("delta")
                    if isinstance(text, str) and text.strip():
                        final_text = text.strip()
                    continue

                if event_type == RESPONSE_STREAMING_EVENTS.response.completed:
                    response_payload = self._coerce_optional_dict(
                        payload.get("response")
                    )
                    if response_payload is None:
                        continue
                    completed = self._extract_output_text(response_payload)
                    if completed:
                        return completed
        finally:
            if callable(close):
                close()

        output = final_text or "".join(deltas).strip()
        if output:
            return output
        raise AiClientError("OpenAI returned no assistant text.")

    def _extract_output_text(self, payload: dict[str, object]) -> str | None:
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        output = payload.get("output")
        if not isinstance(output, list):
            return None

        parts: list[str] = []
        for item in output:
            item_payload = self._coerce_optional_dict(item)
            if item_payload is None:
                continue
            content = item_payload.get("content")
            if not isinstance(content, list):
                continue
            for entry in content:
                entry_payload = self._coerce_optional_dict(entry)
                if entry_payload is None:
                    continue
                text = entry_payload.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        if parts:
            return "\n\n".join(parts)
        return None

    def _coerce_optional_dict(self, value: object) -> dict[str, object] | None:
        if isinstance(value, dict):
            return cast(dict[str, object], value)

        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump(mode="python")
            if isinstance(dumped, dict):
                return cast(dict[str, object], dumped)

        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            dumped = to_dict()
            if isinstance(dumped, dict):
                return cast(dict[str, object], dumped)

        return None

    def _sanitize_session_title(self, title: str) -> str | None:
        sanitized = " ".join(title.strip().split())
        sanitized = sanitized.strip("'\"“”‘’`「」[](){}<>")
        sanitized = re.sub(r"^[\-•*#\d\s.:]+", "", sanitized)
        sanitized = re.sub(r"[.?!。！？]+$", "", sanitized)
        sanitized = re.split(r"[\r\n]", sanitized, maxsplit=1)[0].strip()
        if not sanitized:
            return None
        return sanitized[:30].rstrip()

    def _fallback_session_title(self, user_message: str) -> str:
        cleaned = re.sub(r"\s+", " ", user_message).strip()
        cleaned = cleaned.strip("'\"“”‘’`「」[](){}<>")
        cleaned = re.sub(r"[?!.。！？]+$", "", cleaned)
        first_chunk = re.split(r"[.?!。！？\n]+", cleaned, maxsplit=1)[0].strip()
        if len(first_chunk) >= 12:
            cleaned = first_chunk
        if not cleaned:
            return "새 분석 요청"
        if len(cleaned) <= 30:
            return cleaned
        return f"{cleaned[:29].rstrip()}…"

    def _filter_dataset_ids(self, dataset_ids: list[str]) -> list[str]:
        # multipart form에서 넘어온 업로드 데이터셋 ID 중 빈 값과 중복을 제거합니다.
        return self._dedupe_dataset_ids(dataset_ids)

    def _dedupe_dataset_ids(self, dataset_ids: list[str]) -> list[str]:
        seen: set[str] = set()
        resolved_dataset_ids: list[str] = []
        for dataset_id in dataset_ids:
            normalized_dataset_id = dataset_id.strip()
            if not normalized_dataset_id or normalized_dataset_id in seen:
                continue
            seen.add(normalized_dataset_id)
            resolved_dataset_ids.append(normalized_dataset_id)
        return resolved_dataset_ids

    def _encode_sse_event(self, event: dict[str, object]) -> str:
        event_type = event.get("type")
        # 이벤트 타입이 없으면 SSE 기본 이벤트명인 message로 보냅니다.
        if not isinstance(event_type, str) or not event_type:
            event_type = "message"
        encoded = json.dumps(event, ensure_ascii=False)
        return f"event: {event_type}\ndata: {encoded}\n\n"
