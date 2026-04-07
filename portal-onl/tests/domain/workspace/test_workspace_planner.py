import logging

from domain.shared import AnalyticsPayload, ChartPayload, ChartSeries
from domain.workspace.service import WorkspacePlanner


class PartialWorkspaceLlmClient:
    def generate_json(  # type: ignore[no-untyped-def]
        self, system: str, user_message: str, dataset_ids: list[str] | None = None
    ) -> dict[str, object]:
        del system, user_message, dataset_ids
        return {
            "description": "partial planner output",
            "sections": [{"kind": "chart", "chart_index": 0, "title": "Primary Chart"}],
        }


def test_workspace_planner_accepts_partial_llm_payload(caplog) -> None:
    analytics = AnalyticsPayload(
        charts=[
            ChartPayload(
                type="bar",
                title="Spend by Channel",
                x=["social"],
                series=[ChartSeries(name="Spend", data=[1200])],
            )
        ]
    )
    planner = WorkspacePlanner(llm_client=PartialWorkspaceLlmClient())

    with caplog.at_level(logging.WARNING):
        workspace = planner.plan(
            prompt="채널별 비교해줘",
            analytics=analytics,
            analysis_type="grouped_aggregation",
        )

    assert workspace is not None
    assert workspace.template_id == "comparison_board"
    assert workspace.title == "Comparison Board Workspace"
    assert len(workspace.sections) == 1
    assert workspace.sections[0].kind == "chart"
    assert "Workspace planning fell back to heuristic" not in caplog.text
