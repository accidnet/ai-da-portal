from agents.runtimes.base import BaseAgent
from domain.analyses.service import AnalysisService
from application.datasets.service import DatasetApplicationService
from infrastructure.ai.client import AiClient


class ChatAgent(BaseAgent):
    pass


def build_chat_agent(
    *,
    llm_client: AiClient,
    dataset_service: DatasetApplicationService,
    analysis_service: AnalysisService,
) -> ChatAgent:
    return ChatAgent(
        llm_client=llm_client,
        dataset_service=dataset_service,
        analysis_service=analysis_service,
    )
