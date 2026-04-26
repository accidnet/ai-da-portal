import json
import logging
from collections.abc import Iterable
from typing import cast

from pydantic import BaseModel, Field

from agents.state import AgentRoute
from domain.shared import AnalyticsPayload, WorkspacePayload, WorkspaceSectionPayload
from infrastructure.llm.client import LlmClient, LlmClientError
from infrastructure.llm.streaming_events import RESPONSE_STREAMING_EVENTS


logger = logging.getLogger(__name__)


class PlannedWorkspacePayload(BaseModel):
    template_id: str | None = None
    title: str | None = None
    description: str | None = None
    sections: list[WorkspaceSectionPayload] = Field(default_factory=list)


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
                planned = self._resolve_planned_workspace(
                    self._llm_client.generate_json(
                        system=self._workspace_system_prompt(),
                        user_message=self._compose_planning_message(
                            prompt=prompt,
                            analytics=analytics,
                            route=route,
                            analysis_type=analysis_type,
                        ),
                        dataset_ids=dataset_ids,
                    ),
                )
                workspace = self._build_workspace_from_plan(
                    planned=planned,
                    prompt=prompt,
                    analytics=analytics,
                    route=route,
                    analysis_type=analysis_type,
                )
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

    def _resolve_planned_workspace(self, generated: object) -> dict[str, object]:
        if isinstance(generated, dict):
            return generated
        raw = self._resolve_generated_text(generated)
        return self._extract_json_object(raw)

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
                    response_payload = self._coerce_optional_dict(payload.get("response"))
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
        raise LlmClientError("OpenAI returned invalid JSON for structured output.")

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
                    continue
                json_value = entry_payload.get("json")
                if isinstance(json_value, dict):
                    parts.append(json.dumps(json_value, ensure_ascii=False))
        if parts:
            return "\n\n".join(parts)
        return None

    def _extract_json_object(self, raw_text: str) -> dict[str, object]:
        normalized = raw_text.strip()
        if not normalized:
            raise LlmClientError("OpenAI returned invalid JSON for structured output.")

        fence_start = normalized.find("```")
        if fence_start >= 0:
            fence_end = normalized.rfind("```")
            if fence_end > fence_start:
                normalized = normalized[fence_start + 3 : fence_end].strip()
                if normalized.startswith("json"):
                    normalized = normalized[4:].strip()
        elif not normalized.startswith("{"):
            start = normalized.find("{")
            end = normalized.rfind("}")
            if start >= 0 and end > start:
                normalized = normalized[start : end + 1]

        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError as exc:
            raise LlmClientError(
                "OpenAI returned invalid JSON for structured output."
            ) from exc

        if not isinstance(payload, dict):
            raise LlmClientError(
                "OpenAI returned non-object JSON for structured output."
            )
        return payload

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

    def _workspace_system_prompt(self) -> str:
        return (
            "당신은 데이터 분석 포털의 워크스페이스 레이아웃을 설계합니다. "
            "반드시 JSON만 반환하세요. template_id는 overview, chart_focus, "
            "table_focus, dataset_profile, executive_summary, correlation_focus, "
            "trend_story, anomaly_watch, comparison_board 중 하나만 선택하세요. "
            "section 종류는 summary_cards, chart, table, insight, dataset_profile 중에서만 고르세요. "
            "chart, table, insight 인덱스는 해당 항목이 실제로 존재할 때만 사용하세요. "
            "전체 섹션 수는 3~5개를 선호하고, 제목은 짧게 유지하세요."
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
                f"사용자 요청:\n{prompt or ''}",
                f"라우트: {route or 'n/a'}",
                f"분석 유형: {analysis_type or 'n/a'}",
                (
                    "아래 JSON 스키마 형태로만 반환하세요:\n"
                    '{"template_id":"correlation_focus","title":"...","description":"...",'
                    '"sections":[{"kind":"summary_cards","title":"...","max_items":4,'
                    '"summary_card_labels":["Rows"]},{"kind":"chart","chart_index":0},'
                    '{"kind":"table","table_index":0},{"kind":"insight","insight_index":0},'
                    '{"kind":"dataset_profile"}]}'
                ),
                "사용 가능한 analytics payload:\n"
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
            "correlation_focus": [
                WorkspaceSectionPayload(
                    kind="chart", title="Correlation Matrix", chart_index=0
                ),
                WorkspaceSectionPayload(
                    kind="summary_cards",
                    title="Correlation Signals",
                    max_items=3,
                    summary_card_labels=["Numeric Columns", "Missing Cells", "Rows"],
                ),
                WorkspaceSectionPayload(
                    kind="table", title="Pair Breakdown", table_index=0
                ),
                WorkspaceSectionPayload(
                    kind="insight", title="Strongest Relationship", insight_index=0
                ),
            ],
            "trend_story": [
                WorkspaceSectionPayload(
                    kind="chart", title="Trend Narrative", chart_index=0
                ),
                WorkspaceSectionPayload(
                    kind="insight", title="What Changed", insight_index=0
                ),
                WorkspaceSectionPayload(
                    kind="summary_cards",
                    title="Trend Snapshot",
                    max_items=3,
                    summary_card_labels=["Rows", "Numeric Columns", "Missing Cells"],
                ),
                WorkspaceSectionPayload(
                    kind="table", title="Recent Values", table_index=0
                ),
            ],
            "anomaly_watch": [
                WorkspaceSectionPayload(
                    kind="summary_cards",
                    title="Risk Signals",
                    max_items=4,
                    summary_card_labels=["Missing Cells", "Rows", "Numeric Columns"],
                ),
                WorkspaceSectionPayload(
                    kind="table", title="Flagged Rows", table_index=0
                ),
                WorkspaceSectionPayload(
                    kind="chart", title="Outlier Context", chart_index=0
                ),
                WorkspaceSectionPayload(
                    kind="insight", title="Investigation Note", insight_index=0
                ),
            ],
            "comparison_board": [
                WorkspaceSectionPayload(
                    kind="summary_cards", title="Comparison Snapshot", max_items=4
                ),
                WorkspaceSectionPayload(
                    kind="table", title="Segment Comparison", table_index=0
                ),
                WorkspaceSectionPayload(
                    kind="chart", title="Comparison Chart", chart_index=0
                ),
                WorkspaceSectionPayload(
                    kind="insight", title="Best Segment", insight_index=0
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

    def _build_workspace_from_plan(
        self,
        *,
        planned: dict[str, object],
        prompt: str | None,
        analytics: AnalyticsPayload,
        route: AgentRoute | None,
        analysis_type: str | None,
    ) -> WorkspacePayload:
        partial = PlannedWorkspacePayload.model_validate(planned)
        template_id = partial.template_id or self._infer_template_id(
            prompt=prompt,
            analytics=analytics,
            route=route,
            analysis_type=analysis_type,
        )
        title = partial.title or self._build_title(template_id, analysis_type)
        return WorkspacePayload(
            template_id=template_id,
            title=title,
            description=partial.description,
            sections=partial.sections,
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
        if analysis_type == "anomaly_detection" or self._contains_any(
            lowered, "anomaly", "outlier", "이상치", "이상"
        ):
            return "anomaly_watch"
        if analysis_type == "trend" or self._contains_any(
            lowered, "trend", "forecast", "time", "추세", "시계열"
        ):
            return "trend_story"
        if (
            analysis_type == "correlation"
            or "correlation" in lowered
            or "상관" in lowered
        ):
            return "correlation_focus"
        if (
            analysis_type == "grouped_aggregation"
            or "table" in lowered
            or "breakdown" in lowered
        ):
            return "comparison_board"
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
        if template_id == "correlation_focus":
            return "Correlation Focus Workspace"
        if template_id == "trend_story":
            return "Trend Story Workspace"
        if template_id == "anomaly_watch":
            return "Anomaly Watch Workspace"
        if template_id == "comparison_board":
            return "Comparison Board Workspace"
        if analysis_type:
            return f"{analysis_type.replace('_', ' ').title()} Workspace"
        return "Analysis Workspace"

    def _contains_any(self, message: str, *keywords: str) -> bool:
        return any(keyword in message for keyword in keywords)

    def _has_index(self, index: int | None, items: list[object]) -> bool:
        return index is not None and 0 <= index < len(items)
