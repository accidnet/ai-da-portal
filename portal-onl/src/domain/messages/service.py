import logging
import re
from collections.abc import Generator, Iterable
from typing import cast

from fastapi import UploadFile

from agents.graph import AgentGraph
from agents.state import AgentRoute
from domain.datasets.service import DatasetService
from domain.messages.schemas import (
    ChatInteractionDataset,
    ChatInteractionResponse,
    ChatRequest,
    ChatResponse,
)
from domain.shared import AnalyticsPayload
from domain.sessions.service import SessionService
from infrastructure.llm.client import LlmClient, LlmClientError
from infrastructure.llm.streaming_events import RESPONSE_STREAMING_EVENTS


logger = logging.getLogger(__name__)


class MessageService:
    def __init__(
        self,
        llm_client: LlmClient,
        dataset_service: DatasetService,
        session_service: SessionService,
    ) -> None:
        self._llm_client = llm_client
        self._dataset_service = dataset_service
        self._session_service = session_service

    def handle_chat(
        self, payload: ChatRequest, agent_runtime: AgentGraph
    ) -> ChatResponse:
        agent_runtime = cast(AgentGraph, agent_runtime)
        session = self._session_service.ensure_session(payload.session_id)
        session_title = self._resolve_session_title(
            session_id=payload.session_id,
            current_title=session.title,
            user_message=payload.message,
        )
        session_dataset_ids = self._session_service.get_dataset_ids(payload.session_id)
        logger.debug(
            "Handling chat session_id=%s dataset_ids=%s session_dataset_ids=%s",
            payload.session_id,
            payload.dataset_ids,
            session_dataset_ids,
        )
        state = agent_runtime.invoke(
            {
                "session_id": payload.session_id,
                "message": payload.message,
                "dataset_ids": payload.dataset_ids,
                "session_dataset_ids": session_dataset_ids,
            }
        )
        snapshot = self._snapshot_state(agent_runtime, state)
        logger.debug(
            "Agent graph completed session_id=%s route=%s tools=%s has_analytics=%s",
            payload.session_id,
            snapshot["route"],
            snapshot["used_tools"],
            snapshot["analytics"] is not None,
        )

        snapshot_dataset_ids = payload.dataset_ids or session_dataset_ids
        resolved_dataset_id = snapshot["resolved_dataset_id"]
        if resolved_dataset_id is not None:
            snapshot_dataset_ids = [resolved_dataset_id, *snapshot_dataset_ids]

        self._session_service.record_chat(
            session_id=payload.session_id,
            user_message=payload.message,
            assistant_message=snapshot["assistant_message"],
            route=snapshot["route"],
            used_tools=snapshot["used_tools"],
            plan=snapshot["plan"],
            plan_explanation=snapshot["plan_explanation"],
            dataset_ids=snapshot_dataset_ids,
            analytics=snapshot["analytics"],
            workspace=snapshot["workspace"],
        )

        return ChatResponse(
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
        )

    def stream_chat(
        self, payload: ChatRequest, agent_runtime: AgentGraph
    ) -> Generator[dict[str, object], None, None]:
        agent_runtime = cast(AgentGraph, agent_runtime)
        session = self._session_service.ensure_session(payload.session_id)
        session_title = self._resolve_session_title(
            session_id=payload.session_id,
            current_title=session.title,
            user_message=payload.message,
        )
        session_dataset_ids = self._session_service.get_dataset_ids(payload.session_id)
        logger.debug(
            "Streaming chat session_id=%s dataset_ids=%s session_dataset_ids=%s",
            payload.session_id,
            payload.dataset_ids,
            session_dataset_ids,
        )

        state = yield from agent_runtime.stream_invoke(
            {
                "session_id": payload.session_id,
                "message": payload.message,
                "dataset_ids": payload.dataset_ids,
                "session_dataset_ids": session_dataset_ids,
            }
        )

        snapshot = self._snapshot_state(agent_runtime, state)

        snapshot_dataset_ids = payload.dataset_ids or session_dataset_ids
        resolved_dataset_id = snapshot["resolved_dataset_id"]
        if resolved_dataset_id is not None:
            snapshot_dataset_ids = [resolved_dataset_id, *snapshot_dataset_ids]

        self._session_service.record_chat(
            session_id=payload.session_id,
            user_message=payload.message,
            assistant_message=snapshot["assistant_message"],
            route=snapshot["route"],
            used_tools=snapshot["used_tools"],
            plan=snapshot["plan"],
            plan_explanation=snapshot["plan_explanation"],
            dataset_ids=snapshot_dataset_ids,
            analytics=snapshot["analytics"],
            workspace=snapshot["workspace"],
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

    async def handle_chat_interaction(
        self,
        *,
        session_id: str,
        message: str,
        dataset_ids: list[str],
        file: UploadFile | None,
        agent_runtime: AgentGraph,
    ) -> ChatInteractionResponse:
        resolved_dataset_ids = list(dataset_ids)
        interaction_dataset: ChatInteractionDataset | None = None

        if file is not None:
            detail = await self._dataset_service.upload(file, session_id=session_id)
            preview = self._dataset_service.get_preview(detail.id)
            profile = self._dataset_service.get_profile(detail.id)
            interaction_dataset = ChatInteractionDataset(
                detail=detail,
                preview=preview,
                profile=profile,
            )
            resolved_dataset_ids = [detail.id, *resolved_dataset_ids]

        response = self.handle_chat(
            ChatRequest(
                session_id=session_id,
                message=message,
                dataset_ids=resolved_dataset_ids,
            ),
            agent_runtime=agent_runtime,
        )

        return ChatInteractionResponse(
            **response.model_dump(), dataset=interaction_dataset
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
        self, agent_runtime: AgentGraph, state: dict[str, object]
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
        except LlmClientError as exc:
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
        raise LlmClientError("OpenAI returned no assistant text.")

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
