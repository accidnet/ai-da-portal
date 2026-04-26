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


class FakeStream:
    def __init__(self, events: list[object]) -> None:
        self._events = events
        self.closed = False

    def __iter__(self):
        return iter(self._events)

    def close(self) -> None:
        self.closed = True


class StreamingWorkspaceLlmClient:
    def __init__(self) -> None:
        self.stream = FakeStream(
            [
                {
                    "type": "response.output_text.delta",
                    "delta": '{"template_id":"comparison_board",',
                },
                {
                    "type": "response.output_text.done",
                    "text": (
                        '{"template_id":"comparison_board","title":"Workspace",'
                        '"sections":[{"kind":"chart","chart_index":0}]}'
                    ),
                },
            ]
        )

    def generate_json(  # type: ignore[no-untyped-def]
        self, system: str, user_message: str, dataset_ids: list[str] | None = None
    ) -> object:
        del system, user_message, dataset_ids
        return self.stream


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


def test_workspace_planner_consumes_streamed_json_payload() -> None:
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
    llm_client = StreamingWorkspaceLlmClient()
    planner = WorkspacePlanner(llm_client=llm_client)

    workspace = planner.plan(
        prompt="채널별 비교해줘",
        analytics=analytics,
        analysis_type="grouped_aggregation",
    )

    assert workspace is not None
    assert workspace.template_id == "comparison_board"
    assert len(workspace.sections) == 1
    assert workspace.sections[0].kind == "chart"
    assert llm_client.stream.closed is True
