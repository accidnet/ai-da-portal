import json
import logging

from agents.state import AgentRoute
from domain.shared import AnalyticsPayload, WorkspacePayload, WorkspaceSectionPayload
from infrastructure.llm.client import LlmClient, LlmClientError


logger = logging.getLogger(__name__)


class WorkspacePlanner:
    def __init__(self, llm_client: LlmClient | None = None) -> None:
        self._llm_client = llm_client

    def plan(
        self,
        *,
        prompt: str | None,
        analytics: AnalyticsPayload | None,
        route: AgentRoute | None = None,
        analysis_type: str | None = None,
        dataset_ids: list[str] | None = None,
    ) -> WorkspacePayload | None:
        if analytics is None:
            return None

        if self._llm_client is not None:
            try:
                planned = self._llm_client.generate_json(
                    system=self._workspace_system_prompt(),
                    user_message=self._compose_planning_message(
                        prompt=prompt,
                        analytics=analytics,
                        route=route,
                        analysis_type=analysis_type,
                    ),
                    dataset_ids=dataset_ids,
                )
                workspace = WorkspacePayload.model_validate(planned)
                sanitized = self._sanitize_workspace(workspace, analytics)
                if sanitized.sections:
                    return sanitized
            except (LlmClientError, ValueError) as exc:
                logger.warning("Workspace planning fell back to heuristic: %s", exc)

        return self._fallback_workspace(
            prompt=prompt,
            analytics=analytics,
            route=route,
            analysis_type=analysis_type,
        )

    def _workspace_system_prompt(self) -> str:
        return (
            "You plan workspace layouts for a data analysis portal. "
            "Return JSON only. Choose one template_id from: overview, chart_focus, "
            "table_focus, dataset_profile, executive_summary. "
            "Choose sections only from: summary_cards, chart, table, insight, dataset_profile. "
            "Use available chart/table/insight indexes only when those items exist. "
            "Prefer 3-5 sections total and keep titles short."
        )

    def _compose_planning_message(
        self,
        *,
        prompt: str | None,
        analytics: AnalyticsPayload,
        route: AgentRoute | None,
        analysis_type: str | None,
    ) -> str:
        return "\n\n".join(
            [
                f"User prompt:\n{prompt or ''}",
                f"Route: {route or 'n/a'}",
                f"Analysis type: {analysis_type or 'n/a'}",
                (
                    "Return this JSON schema only:\n"
                    '{"template_id":"overview","title":"...","description":"...",'
                    '"sections":[{"kind":"summary_cards","title":"...","max_items":4,'
                    '"summary_card_labels":["Rows"]},{"kind":"chart","chart_index":0},'
                    '{"kind":"table","table_index":0},{"kind":"insight","insight_index":0},'
                    '{"kind":"dataset_profile"}]}'
                ),
                "Available analytics payload:\n"
                + json.dumps(analytics.model_dump(mode="json"), ensure_ascii=False),
            ]
        )

    def _sanitize_workspace(
        self, workspace: WorkspacePayload, analytics: AnalyticsPayload
    ) -> WorkspacePayload:
        sections: list[WorkspaceSectionPayload] = []

        for section in workspace.sections:
            if section.kind == "summary_cards" and analytics.summary_cards:
                sections.append(section)
            elif section.kind == "chart" and self._has_index(
                section.chart_index, analytics.charts
            ):
                sections.append(section)
            elif section.kind == "table" and self._has_index(
                section.table_index, analytics.tables
            ):
                sections.append(section)
            elif section.kind == "insight" and self._has_index(
                section.insight_index, analytics.insights
            ):
                sections.append(section)
            elif section.kind == "dataset_profile" and analytics.dataset_profile:
                sections.append(section)

        return WorkspacePayload(
            template_id=workspace.template_id,
            title=workspace.title,
            description=workspace.description,
            sections=sections,
        )

    def _fallback_workspace(
        self,
        *,
        prompt: str | None,
        analytics: AnalyticsPayload,
        route: AgentRoute | None,
        analysis_type: str | None,
    ) -> WorkspacePayload:
        template_id = self._infer_template_id(
            prompt=prompt,
            analytics=analytics,
            route=route,
            analysis_type=analysis_type,
        )
        title = self._build_title(template_id, analysis_type)

        sections_by_template = {
            "overview": [
                WorkspaceSectionPayload(
                    kind="summary_cards", title="Key Metrics", max_items=4
                ),
                WorkspaceSectionPayload(
                    kind="chart", title="Primary Chart", chart_index=0
                ),
                WorkspaceSectionPayload(
                    kind="table", title="Detail Table", table_index=0
                ),
                WorkspaceSectionPayload(
                    kind="insight", title="Recommendation", insight_index=0
                ),
                WorkspaceSectionPayload(
                    kind="dataset_profile", title="Dataset Profile"
                ),
            ],
            "chart_focus": [
                WorkspaceSectionPayload(
                    kind="chart", title="Primary Chart", chart_index=0
                ),
                WorkspaceSectionPayload(
                    kind="summary_cards", title="Supporting Metrics", max_items=4
                ),
                WorkspaceSectionPayload(
                    kind="insight", title="Interpretation", insight_index=0
                ),
                WorkspaceSectionPayload(
                    kind="table", title="Supporting Table", table_index=0
                ),
            ],
            "table_focus": [
                WorkspaceSectionPayload(
                    kind="summary_cards", title="Snapshot", max_items=4
                ),
                WorkspaceSectionPayload(
                    kind="table", title="Detailed Breakdown", table_index=0
                ),
                WorkspaceSectionPayload(
                    kind="chart", title="Visual Check", chart_index=0
                ),
                WorkspaceSectionPayload(
                    kind="insight", title="Next Step", insight_index=0
                ),
            ],
            "dataset_profile": [
                WorkspaceSectionPayload(kind="dataset_profile", title="Profile"),
                WorkspaceSectionPayload(
                    kind="summary_cards", title="Coverage", max_items=4
                ),
                WorkspaceSectionPayload(
                    kind="chart", title="Sample View", chart_index=0
                ),
                WorkspaceSectionPayload(
                    kind="insight", title="Recommended Analysis", insight_index=0
                ),
            ],
            "executive_summary": [
                WorkspaceSectionPayload(
                    kind="insight", title="Executive Summary", insight_index=0
                ),
                WorkspaceSectionPayload(
                    kind="summary_cards", title="Headline Metrics", max_items=4
                ),
                WorkspaceSectionPayload(
                    kind="chart", title="Headline Chart", chart_index=0
                ),
            ],
        }

        return self._sanitize_workspace(
            WorkspacePayload(
                template_id=template_id,
                title=title,
                description="LLM workspace planner fallback layout",
                sections=sections_by_template[template_id],
            ),
            analytics,
        )

    def _infer_template_id(
        self,
        *,
        prompt: str | None,
        analytics: AnalyticsPayload,
        route: AgentRoute | None,
        analysis_type: str | None,
    ) -> str:
        lowered = (prompt or "").lower()
        if analysis_type == "dataset_profile" or route == "dataset_analysis":
            return "dataset_profile"
        if (
            analysis_type == "correlation"
            or "correlation" in lowered
            or "상관" in lowered
        ):
            return "chart_focus"
        if (
            analysis_type == "grouped_aggregation"
            or "table" in lowered
            or "breakdown" in lowered
        ):
            return "table_focus"
        if analytics.insights and (
            "summary" in lowered or "dashboard" in lowered or "요약" in lowered
        ):
            return "executive_summary"
        return "overview"

    def _build_title(self, template_id: str, analysis_type: str | None) -> str:
        if template_id == "dataset_profile":
            return "Dataset Profile Workspace"
        if template_id == "chart_focus":
            return "Chart Focus Workspace"
        if template_id == "table_focus":
            return "Table Focus Workspace"
        if template_id == "executive_summary":
            return "Executive Summary Workspace"
        if analysis_type:
            return f"{analysis_type.replace('_', ' ').title()} Workspace"
        return "Analysis Workspace"

    def _has_index(self, index: int | None, items: list[object]) -> bool:
        return index is not None and 0 <= index < len(items)
