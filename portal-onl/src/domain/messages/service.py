from agents.router import route_message
from agents.state import AgentRoute
from domain.messages.schemas import ChatRequest, ChatResponse
from domain.shared import (
    AnalyticsPayload,
    ChartPayload,
    ChartSeries,
    InsightPayload,
    SummaryCard,
)


class MessageService:
    def handle_chat(self, payload: ChatRequest, agent_runtime: object) -> ChatResponse:
        del agent_runtime
        route = route_message(payload.message, has_dataset=bool(payload.dataset_ids))
        analytics = self._build_analytics(route)
        assistant_message = self._build_reply(route)

        return ChatResponse(
            session_id=payload.session_id,
            assistant_message=assistant_message,
            follow_up_suggestions=self._suggestions(route),
            analytics=analytics,
        )

    def _build_reply(self, route: AgentRoute) -> str:
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

    def _build_analytics(self, route: AgentRoute) -> AnalyticsPayload | None:
        if route == "conversation":
            return None

        return AnalyticsPayload(
            summary_cards=[
                SummaryCard(
                    label="Status",
                    value="Scaffolded",
                    detail="Agent and chart contract are wired",
                ),
                SummaryCard(
                    label="Mode",
                    value=route.replace("_", " ").title(),
                    detail="Ready for tool execution",
                ),
            ],
            charts=[
                ChartPayload(
                    type="line",
                    title="Sample Analysis Output",
                    x=["Step 1", "Step 2", "Step 3"],
                    series=[ChartSeries(name="progress", data=[15, 60, 100])],
                )
            ],
            insights=[
                InsightPayload(
                    title="Next Step",
                    body="Connect upload profiling and dataframe tools to replace placeholder analytics with real dataset-driven output.",
                    action_label="Run Dataset Profile",
                )
            ],
        )
