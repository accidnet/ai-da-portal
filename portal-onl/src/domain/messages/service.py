from agents.router import route_message
from agents.state import AgentRoute
from domain.analyses.schemas import AnalysisRequest
from domain.analyses.service import AnalysisService
from domain.datasets.service import DatasetService
from domain.messages.schemas import ChatRequest, ChatResponse
from domain.shared import AnalyticsPayload
from infrastructure.llm.client import LlmClient


class MessageService:
    def __init__(
        self,
        llm_client: LlmClient,
        dataset_service: DatasetService,
        analysis_service: AnalysisService,
    ) -> None:
        self._llm_client = llm_client
        self._dataset_service = dataset_service
        self._analysis_service = analysis_service

    def handle_chat(self, payload: ChatRequest, agent_runtime: object) -> ChatResponse:
        del agent_runtime
        route = route_message(payload.message, has_dataset=bool(payload.dataset_ids))
        analytics = self._build_analytics(route=route, payload=payload)
        assistant_message = self._build_reply(
            route=route, payload=payload, analytics=analytics
        )

        return ChatResponse(
            session_id=payload.session_id,
            assistant_message=assistant_message,
            follow_up_suggestions=self._suggestions(route),
            analytics=analytics,
        )

    def _build_reply(
        self,
        route: AgentRoute,
        payload: ChatRequest,
        analytics: AnalyticsPayload | None,
    ) -> str:
        llm_reply = self._llm_client.generate(
            system=self._system_prompt(route),
            user_message=payload.message,
            dataset_ids=payload.dataset_ids,
        )
        if llm_reply:
            return llm_reply

        if analytics:
            summary = (
                analytics.summary_cards[0].value
                if analytics.summary_cards
                else "the uploaded dataset"
            )
            return f"I analyzed {summary} and prepared the dashboard output from the live dataset."
        if route == "dataset_analysis":
            return "Uploaded data is the best starting point. I can summarize quality, surface trends, and prepare the first charts for the analytics pane."
        if route == "analysis_request":
            return "That request fits a structured analysis flow. I would profile the selected dataset, run the matching analysis tool, and return charts plus a concise business summary."
        return "I can answer directly, then suggest the most useful next analyses if you upload data or choose a metric to explore."

    def _suggestions(self, route: AgentRoute) -> list[str]:
        if route == "dataset_analysis":
            return [
                "Show missing values and column types first.",
                "Recommend three analyses based on this dataset.",
                "Create an initial trend chart for the main numeric metric.",
            ]
        if route == "analysis_request":
            return [
                "Compare key metrics by month.",
                "Detect anomalies in the target column.",
                "Build a correlation view for numeric columns.",
            ]
        return [
            "Upload a CSV and profile it automatically.",
            "Ask for a trend or correlation analysis.",
            "Request a chart-ready summary for the dashboard.",
        ]

    def _build_analytics(
        self, route: AgentRoute, payload: ChatRequest
    ) -> AnalyticsPayload | None:
        dataset_id = self._resolve_dataset_id(payload.dataset_ids)
        if dataset_id is None:
            return None

        analysis_type = self._route_to_analysis_type(route, payload.message)
        result = self._analysis_service.create(
            AnalysisRequest(
                session_id=payload.session_id,
                dataset_id=dataset_id,
                analysis_type=analysis_type,
                prompt=payload.message,
            )
        )
        return result.analytics

    def _resolve_dataset_id(self, dataset_ids: list[str]) -> str | None:
        if dataset_ids:
            return dataset_ids[0]
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
