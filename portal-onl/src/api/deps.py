from functools import lru_cache

from fastapi import Depends

from agents.runtimes import (
    ChatAgent,
    ChatStreamingAgent,
    build_chat_agent,
    build_chat_streaming_agent,
)
from core.config import Settings, get_settings
from domain.auth.service import OpenAiAuthService, OpenAiAuthStore
from domain.analyses.service import AnalysisService
from domain.datasets.service import DatasetService
from domain.messages.service import MessageService
from domain.messages.stream_service import MessageStreamService
from domain.sessions.service import SessionService
from infrastructure.ai.client import AiClient


def get_app_settings() -> Settings:
    return get_settings()


@lru_cache
def get_session_service() -> SessionService:
    return SessionService()


@lru_cache
def get_openai_auth_store() -> OpenAiAuthStore:
    settings = get_settings()
    return OpenAiAuthStore(settings.openai_auth_storage_path)


@lru_cache
def get_openai_auth_service() -> OpenAiAuthService:
    return OpenAiAuthService(settings=get_settings(), store=get_openai_auth_store())


@lru_cache
def get_llm_client() -> AiClient:
    return AiClient(settings=get_settings(), auth_service=get_openai_auth_service())


@lru_cache
def get_dataset_service() -> DatasetService:
    return DatasetService(session_service=get_session_service())


@lru_cache
def get_analysis_service() -> AnalysisService:
    return AnalysisService(
        dataset_service=get_dataset_service(),
        llm_client=get_llm_client(),
        session_service=get_session_service(),
    )


@lru_cache
def get_message_service() -> MessageService:
    return MessageService(
        llm_client=get_llm_client(),
        dataset_service=get_dataset_service(),
        session_service=get_session_service(),
    )


def get_message_stream_service(
    message_service: MessageService = Depends(get_message_service),
) -> MessageStreamService:
    return MessageStreamService(message_service=message_service)


def get_chat_agent_runtime() -> ChatAgent:
    return build_chat_agent(
        llm_client=get_llm_client(),
        dataset_service=get_dataset_service(),
        analysis_service=get_analysis_service(),
    )


def get_chat_streaming_agent_runtime() -> ChatStreamingAgent:
    return build_chat_streaming_agent(
        llm_client=get_llm_client(),
        dataset_service=get_dataset_service(),
        analysis_service=get_analysis_service(),
    )
