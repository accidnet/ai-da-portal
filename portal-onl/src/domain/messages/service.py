import json
import logging
import re

from fastapi import UploadFile

from agents.router import route_message
from agents.state import AgentRoute
from domain.analyses.schemas import AnalysisDetail
from domain.analyses.schemas import AnalysisRequest
from domain.analyses.service import AnalysisService
from domain.datasets.service import DatasetService
from domain.messages.schemas import (
    ChatInteractionDataset,
    ChatInteractionResponse,
    ChatRequest,
    ChatResponse,
)
from domain.shared import AnalyticsPayload
from domain.sessions.service import SessionService
from domain.workspace.service import WorkspacePlanner
from infrastructure.llm.client import LlmClient, LlmClientError


logger = logging.getLogger(__name__)


class MessageService:
    def __init__(
        self,
        llm_client: LlmClient,
        dataset_service: DatasetService,
        analysis_service: AnalysisService,
        session_service: SessionService,
    ) -> None:
        self._llm_client = llm_client
        self._dataset_service = dataset_service
        self._analysis_service = analysis_service
        self._session_service = session_service
        self._workspace_planner = WorkspacePlanner(llm_client=llm_client)

    def handle_chat(self, payload: ChatRequest, agent_runtime: object) -> ChatResponse:
        del agent_runtime
        session = self._session_service.ensure_session(payload.session_id)
        session_title = self._resolve_session_title(
            session_id=payload.session_id,
            current_title=session.title,
            user_message=payload.message,
        )
        session_dataset_ids = self._session_service.get_dataset_ids(payload.session_id)
        route = route_message(
            payload.message,
            has_dataset=bool(payload.dataset_ids or session_dataset_ids),
        )
        logger.debug(
            "Handling chat session_id=%s route=%s dataset_ids=%s",
            payload.session_id,
            route,
            payload.dataset_ids,
        )
        analysis_detail = self._build_analysis(
            route=route,
            payload=payload,
            session_dataset_ids=session_dataset_ids,
        )
        analytics = analysis_detail.analytics if analysis_detail is not None else None
        workspace = analysis_detail.workspace if analysis_detail is not None else None
        logger.debug(
            "Analytics prepared session_id=%s has_analytics=%s summary_cards=%s charts=%s tables=%s workspace=%s",
            payload.session_id,
            analytics is not None,
            len(analytics.summary_cards) if analytics else 0,
            len(analytics.charts) if analytics else 0,
            len(analytics.tables) if analytics else 0,
            workspace.template_id if workspace else None,
        )
        try:
            assistant_message = self._llm_client.generate(
                system=self._system_prompt(route),
                user_message=self._compose_user_message(
                    payload=payload, analytics=analytics
                ),
                dataset_ids=payload.dataset_ids,
            )
            logger.debug(
                "LLM reply generated session_id=%s reply_len=%s",
                payload.session_id,
                len(assistant_message),
            )
        except LlmClientError as exc:
            logger.warning(
                "LLM reply failed, using fallback session_id=%s route=%s detail=%s",
                payload.session_id,
                route,
                exc,
            )
            assistant_message = self._fallback_assistant_message(
                route=route,
                analytics=analytics,
                dataset_ids=payload.dataset_ids,
            )

        snapshot_dataset_ids = payload.dataset_ids or session_dataset_ids
        if analysis_detail is not None and analysis_detail.dataset_id is not None:
            snapshot_dataset_ids = [analysis_detail.dataset_id, *snapshot_dataset_ids]

        self._session_service.record_chat(
            session_id=payload.session_id,
            user_message=payload.message,
            assistant_message=assistant_message,
            dataset_ids=snapshot_dataset_ids,
            analytics=analytics,
            workspace=workspace,
        )

        return ChatResponse(
            session_id=payload.session_id,
            session_title=session_title,
            assistant_message=assistant_message,
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
        agent_runtime: object,
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

    def _compose_user_message(
        self, payload: ChatRequest, analytics: AnalyticsPayload | None
    ) -> str:
        sections = [f"User request:\n{payload.message}"]

        if payload.dataset_ids:
            sections.append(f"Dataset IDs: {', '.join(payload.dataset_ids)}")

        if analytics is not None:
            sections.append(
                "Structured analytics already prepared for this request:\n"
                + json.dumps(analytics.model_dump(mode="json"), ensure_ascii=False)
            )

        sections.append(
            "Respond with a concise assistant reply that matches the analytics context already generated by the backend."
        )

        return "\n\n".join(sections)

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

    def _build_analysis(
        self,
        route: AgentRoute,
        payload: ChatRequest,
        session_dataset_ids: list[str],
    ) -> AnalysisDetail | None:
        dataset_id = self._resolve_dataset_id(payload.dataset_ids, session_dataset_ids)
        if dataset_id is None:
            logger.debug(
                "Skipping analytics creation session_id=%s no_dataset_resolved",
                payload.session_id,
            )
            return None

        analysis_type = self._route_to_analysis_type(route, payload.message)
        logger.debug(
            "Creating analytics session_id=%s dataset_id=%s analysis_type=%s",
            payload.session_id,
            dataset_id,
            analysis_type,
        )
        result = self._analysis_service.create(
            AnalysisRequest(
                session_id=payload.session_id,
                dataset_id=dataset_id,
                analysis_type=analysis_type,
                prompt=payload.message,
            )
        )
        logger.debug(
            "Analytics created session_id=%s dataset_id=%s status=%s",
            payload.session_id,
            dataset_id,
            result.status,
        )
        return result

    def _resolve_dataset_id(
        self, dataset_ids: list[str], session_dataset_ids: list[str]
    ) -> str | None:
        if dataset_ids:
            return dataset_ids[0]
        if session_dataset_ids:
            return session_dataset_ids[0]
        return self._dataset_service.get_latest_dataset_id()

    def _route_to_analysis_type(self, route: AgentRoute, message: str) -> str:
        lowered = message.lower()
        if route == "dataset_analysis":
            return "dataset_profile"
        if self._contains_any(
            lowered,
            "anomaly",
            "outlier",
            "이상치",
            "이상",
        ):
            return "anomaly_detection"
        if self._contains_any(
            lowered,
            "trend",
            "monthly",
            "time",
            "forecast",
            "추세",
            "월별",
            "시계열",
            "예측",
        ):
            return "trend"
        if self._contains_any(
            lowered,
            "correlation",
            "correlat",
            "relationship",
            "상관",
            "관계",
        ):
            return "correlation"
        if self._contains_any(
            lowered,
            "group",
            "segment",
            "break down",
            "breakdown",
            "compare",
            "by channel",
            "그룹",
            "세그먼트",
            "비교",
            "채널별",
            "구분",
        ):
            return "grouped_aggregation"
        return "descriptive_summary"

    def _contains_any(self, message: str, *keywords: str) -> bool:
        return any(keyword in message for keyword in keywords)

    def _system_prompt(self, route: AgentRoute) -> str:
        if route == "dataset_analysis":
            return (
                "You are a data analysis copilot inside a portal dashboard. "
                "Help the user explore uploaded datasets, summarize quality, and propose the next best analysis."
            )
        if route == "analysis_request":
            return (
                "You are a data analysis copilot inside a portal dashboard. "
                "Return a concise, business-friendly analysis response with specific next steps."
            )
        return (
            "You are a concise AI assistant inside a data portal. "
            "Answer clearly and suggest the next useful dataset or analytics action when relevant."
        )

    def _fallback_assistant_message(
        self,
        *,
        route: AgentRoute,
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
