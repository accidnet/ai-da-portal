import logging
import re
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
        route = cast(AgentRoute, state.get("route", "conversation"))
        assistant_message = state.get("assistant_message", "").strip()
        analytics = state.get("analytics")
        workspace = state.get("workspace")
        used_tools = [
            tool for tool in state.get("used_tools", []) if isinstance(tool, str)
        ]
        plan = list(state.get("plan", []))
        plan_explanation = state.get("plan_explanation")
        logger.debug(
            "Agent graph completed session_id=%s route=%s tools=%s has_analytics=%s",
            payload.session_id,
            route,
            used_tools,
            analytics is not None,
        )
        if not assistant_message:
            assistant_message = self._fallback_assistant_message(
                route=route,
                analytics=analytics,
                dataset_ids=payload.dataset_ids,
            )

        snapshot_dataset_ids = payload.dataset_ids or session_dataset_ids
        resolved_dataset_id = state.get("resolved_dataset_id")
        if resolved_dataset_id is not None:
            snapshot_dataset_ids = [resolved_dataset_id, *snapshot_dataset_ids]

        self._session_service.record_chat(
            session_id=payload.session_id,
            user_message=payload.message,
            assistant_message=assistant_message,
            route=route,
            used_tools=used_tools,
            plan=plan,
            plan_explanation=plan_explanation
            if isinstance(plan_explanation, str)
            else None,
            dataset_ids=snapshot_dataset_ids,
            analytics=analytics,
            workspace=workspace,
        )

        return ChatResponse(
            session_id=payload.session_id,
            session_title=session_title,
            assistant_message=assistant_message,
            route=route,
            used_tools=used_tools,
            plan=plan,
            plan_explanation=plan_explanation
            if isinstance(plan_explanation, str)
            else None,
            analytics=analytics,
            workspace=workspace,
        )

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
            sanitized = self._sanitize_session_title(generated)
            if sanitized:
                return sanitized
        except LlmClientError as exc:
            logger.info(
                "Session title generation failed; using fallback detail=%s", exc
            )

        return self._fallback_session_title(user_message)

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

    def _fallback_assistant_message(
        self,
        *,
        route: str,
        analytics: AnalyticsPayload | None,
        dataset_ids: list[str],
    ) -> str:
        if analytics is not None and analytics.insights:
            lead = analytics.insights[0].body
            return f"백엔드 분석은 완료됐어요. {lead}"

        if dataset_ids and route == "dataset_analysis":
            return "파일을 받아서 기본 프로파일링을 완료했어요. 오른쪽 Workspace에서 데이터 개요를 확인해보세요."

        if route == "analysis_request":
            return "요청한 분석을 실행했어요. 오른쪽 Workspace에 결과 카드와 표를 반영했습니다."

        return "요청을 처리했어요. 추가로 궁금한 점이나 더 보고 싶은 분석이 있으면 이어서 입력해 주세요."
