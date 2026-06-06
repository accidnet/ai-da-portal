from functools import lru_cache

from features.agents.runtimes import (
    ChatStreamingAgent,
    build_chat_streaming_agent,
)
from core.config import Settings, get_settings
from features.auth.api.deps import get_openai_auth_service
from features.datasets.application.service import DatasetApplicationService
from domain.messages.stream_service import MessageStreamService
from features.workspaces.application.local_storage import WorkspaceLocalStorage
from features.workspaces.application.dataset_materializer import (
    WorkspaceDatasetMaterializer,
)
from domain.sessions.service import SessionService
from domain.sessions.title_service import SessionTitleService
from features.workspaces.application.usecase import WorkspaceUsecase
from features.workspaces.infrastructure.repositories import WorkspaceRepository
from features.data_sources.infrastructure.repositories import DataSourceRepository
from infrastructure.ai.client import AiClient
from infrastructure.ai.openai_client import OpenAiProvider
from infrastructure.db.repositories import (
    DatasetRepository,
    MessageRepository,
    SessionRepository,
)


def get_app_settings() -> Settings:
    return get_settings()


@lru_cache
def get_session_repository() -> SessionRepository:
    return SessionRepository()


@lru_cache
def get_message_repository() -> MessageRepository:
    return MessageRepository()


@lru_cache
def get_dataset_repository() -> DatasetRepository:
    return DatasetRepository()


@lru_cache
def get_workspace_repository() -> WorkspaceRepository:
    return WorkspaceRepository()


@lru_cache
def get_workspace_local_storage() -> WorkspaceLocalStorage:
    settings = get_settings()
    return WorkspaceLocalStorage(
        root_dir=settings.workspace_storage_dir,
        ttl_seconds=settings.workspace_storage_ttl_seconds,
    )


@lru_cache
def get_data_source_repository() -> DataSourceRepository:
    return DataSourceRepository()


@lru_cache
def get_workspace_dataset_materializer() -> WorkspaceDatasetMaterializer:
    return WorkspaceDatasetMaterializer(
        dataset_repository=get_dataset_repository(),
        data_source_repository=get_data_source_repository(),
    )


@lru_cache
def get_session_service() -> SessionService:
    return SessionService(
        repository=get_session_repository(),
        message_repository=get_message_repository(),
    )


@lru_cache
def get_workspace_usecase() -> WorkspaceUsecase:
    return WorkspaceUsecase(
        repository=get_workspace_repository(),
        local_storage=get_workspace_local_storage(),
    )


@lru_cache
def get_llm_client() -> AiClient:
    return AiClient(
        provider=OpenAiProvider(
            settings=get_settings(),
            auth_service=get_openai_auth_service(),
        )
    )


@lru_cache
def get_dataset_service() -> DatasetApplicationService:
    return DatasetApplicationService(
        dataset_repository=get_dataset_repository(),
        session_service=get_session_service(),
        data_source_repository=get_data_source_repository(),
    )


def get_message_stream_service() -> MessageStreamService:
    return MessageStreamService(
        session_service=get_session_service(),
        message_repository=get_message_repository(),
        workspace_local_storage=get_workspace_local_storage(),
        workspace_dataset_materializer=get_workspace_dataset_materializer(),
        workspace_repository=get_workspace_repository(),
    )


def get_session_title_service() -> SessionTitleService:
    return SessionTitleService(
        llm_client=get_llm_client(),
        session_service=get_session_service(),
    )


def get_chat_streaming_agent_runtime() -> ChatStreamingAgent:
    return build_chat_streaming_agent(
        llm_client=get_llm_client(),
        dataset_service=get_dataset_service(),
    )
