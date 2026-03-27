from agents.graph import build_agent_graph
from core.config import Settings, get_settings
from domain.analyses.service import AnalysisService
from domain.datasets.service import DatasetService
from domain.messages.service import MessageService
from domain.sessions.service import SessionService


def get_app_settings() -> Settings:
    return get_settings()


def get_session_service() -> SessionService:
    return SessionService()


def get_message_service() -> MessageService:
    return MessageService()


def get_dataset_service() -> DatasetService:
    return DatasetService()


def get_analysis_service() -> AnalysisService:
    return AnalysisService()


def get_agent_runtime() -> object:
    return build_agent_graph()
