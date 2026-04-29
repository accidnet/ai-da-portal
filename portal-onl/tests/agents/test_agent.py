from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from agents.agent import Agent
from domain.analyses.schemas import AnalysisDetail
from domain.datasets.schemas import DatasetDetail, DatasetPreviewResponse, DatasetProfileResponse
from domain.shared import (
    AnalyticsPayload,
    DatasetColumnProfile,
    DatasetProfilePayload,
    InsightPayload,
    SummaryCard,
    WorkspacePayload,
    WorkspaceSectionPayload,
)


class FakeAiClient:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self._responses = responses
        self.calls: list[dict[str, object]] = []

    def create_response(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        return self._responses.pop(0)


class FakeStream:
    def __init__(self, events: list[object]) -> None:
        self._events = events
        self.closed = False

    def __iter__(self):
        return iter(self._events)

    def close(self) -> None:
        self.closed = True


class FakeDatasetService:
    def __init__(self) -> None:
        self._loaded_paths: list[str] = []

    def get_latest_dataset_id(self) -> str | None:
        return "dataset-1"

    def get(self, dataset_id: str) -> DatasetDetail:
        assert dataset_id == "dataset-1"
        return DatasetDetail(
            id=dataset_id,
            filename="sales.csv",
            content_type="text/csv",
            storage_path="/tmp/dataset-1__sales.csv",
            created_at=datetime.now(UTC),
        )

    def get_uploaded_filenames(self, dataset_ids: list[str]) -> list[str]:
        assert dataset_ids
        return ["sales.csv"]

    def get_profile(self, dataset_id: str) -> DatasetProfileResponse:
        assert dataset_id == "dataset-1"
        return DatasetProfileResponse(
            dataset_id=dataset_id,
            profile=DatasetProfilePayload(
                row_count=12,
                column_count=2,
                columns=[
                    DatasetColumnProfile(name="sales", dtype="int"),
                    DatasetColumnProfile(name="region", dtype="string"),
                ],
                suggested_prompts=["매출 상관관계를 분석해줘"],
            ),
        )

    def get_preview(self, dataset_id: str) -> DatasetPreviewResponse:
        assert dataset_id == "dataset-1"
        return DatasetPreviewResponse(
            dataset_id=dataset_id,
            columns=["sales", "region"],
            rows=[{"sales": 100, "region": "KR"}],
        )

    def load_uploaded_file_by_filename(self, filename: str) -> dict[str, object]:
        assert filename == "sales.csv"
        self._loaded_paths.append(filename)
        dataframe = pd.DataFrame(
            [{"sales": 100, "region": "KR"}, {"sales": 120, "region": "US"}]
        )
        return {
            "filename": filename,
            "dataset_id": "dataset-1",
            "storage_path": str(Path("/tmp/dataset-1__sales.csv")),
            "row_count": 2,
            "column_count": 2,
            "columns": ["sales", "region"],
            "dtypes": {"sales": "int64", "region": "object"},
            "null_counts": {"sales": 0, "region": 0},
            "preview": {
                "columns": ["sales", "region"],
                "rows": dataframe.to_dict(orient="records"),
            },
        }


class FakeAnalysisService:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def create(self, payload):  # type: ignore[no-untyped-def]
        self.calls.append(payload)
        return AnalysisDetail(
            id="analysis-1",
            session_id=payload.session_id,
            dataset_id=payload.dataset_id,
            analysis_type=payload.analysis_type,
            status="completed",
            created_at=datetime.now(UTC),
            analytics=AnalyticsPayload(
                summary_cards=[SummaryCard(label="Rows", value="12")],
                insights=[InsightPayload(title="핵심", body="매출이 증가 추세입니다.")],
            ),
            workspace=WorkspacePayload(
                template_id="overview",
                title="Analysis Workspace",
                sections=[WorkspaceSectionPayload(kind="summary_cards")],
            ),
        )


def test_agent_graph_returns_direct_conversation_reply() -> None:
    llm_client = FakeAiClient(
        [{"id": "resp_1", "output_text": "안녕하세요. 무엇을 도와드릴까요?"}]
    )
    graph = Agent(
        llm_client=llm_client,
        dataset_service=FakeDatasetService(),
        analysis_service=FakeAnalysisService(),
    )

    result = graph.invoke(
        {
            "session_id": "session-1",
            "message": "안녕",
            "dataset_ids": [],
            "session_dataset_ids": [],
        }
    )

    assert result["assistant_message"] == "안녕하세요. 무엇을 도와드릴까요?"
    assert result["route"] == "conversation"
    assert result["used_tools"] == []
    assert llm_client.calls[0]["input"][0]["content"][0]["text"]


def test_agent_initial_input_includes_uploaded_filenames() -> None:
    llm_client = FakeAiClient(
        [{"id": "resp_1", "output_text": "파일명을 확인했습니다."}]
    )
    graph = Agent(
        llm_client=llm_client,
        dataset_service=FakeDatasetService(),
        analysis_service=FakeAnalysisService(),
    )

    graph.invoke(
        {
            "session_id": "session-1",
            "message": "업로드 파일을 확인해줘",
            "dataset_ids": ["dataset-1"],
            "session_dataset_ids": [],
        }
    )

    payload = llm_client.calls[0]["input"][0]["content"][0]["text"]
    assert '"available_uploaded_filenames": ["sales.csv"]' in payload
    assert '"latest_uploaded_filename": "sales.csv"' in payload


def test_agent_loads_uploaded_file_by_filename_tool() -> None:
    dataset_service = FakeDatasetService()
    graph = Agent(
        llm_client=FakeAiClient(
            [
                {
                    "id": "resp_1",
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "call_1",
                            "name": "load_uploaded_dataset_file",
                            "arguments": '{"filename":"sales.csv"}',
                        }
                    ],
                },
                {
                    "id": "resp_2",
                    "output_text": "sales.csv 파일을 로드했고 기본 정보를 확인했습니다.",
                },
            ]
        ),
        dataset_service=dataset_service,
        analysis_service=FakeAnalysisService(),
    )

    result = graph.invoke(
        {
            "session_id": "session-1",
            "message": "sales.csv를 불러와서 구조를 보여줘",
            "dataset_ids": ["dataset-1"],
            "session_dataset_ids": [],
        }
    )

    assert result["assistant_message"] == "sales.csv 파일을 로드했고 기본 정보를 확인했습니다."
    assert result["used_tools"] == ["load_uploaded_dataset_file"]
    assert dataset_service._loaded_paths == ["sales.csv"]


def test_agent_graph_uses_dataset_context_tool_before_reply() -> None:
    llm_client = FakeAiClient(
        [
            {
                "id": "resp_1",
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "inspect_dataset_context",
                        "arguments": '{"include_preview":true,"include_profile":true}',
                    }
                ],
            },
            {
                "id": "resp_2",
                "output_text": "데이터셋은 12행 2열이고 sales 컬럼이 있습니다.",
            },
        ]
    )
    graph = Agent(
        llm_client=llm_client,
        dataset_service=FakeDatasetService(),
        analysis_service=FakeAnalysisService(),
    )

    result = graph.invoke(
        {
            "session_id": "session-1",
            "message": "업로드된 데이터 컬럼을 설명해줘",
            "dataset_ids": [],
            "session_dataset_ids": ["dataset-1"],
        }
    )

    assert (
        result["assistant_message"] == "데이터셋은 12행 2열이고 sales 컬럼이 있습니다."
    )
    assert result["route"] == "dataset_analysis"
    assert result["resolved_dataset_id"] == "dataset-1"
    assert result["used_tools"] == ["inspect_dataset_context"]


def test_agent_graph_runs_analysis_tool_and_keeps_structured_outputs() -> None:
    analysis_service = FakeAnalysisService()
    graph = Agent(
        llm_client=FakeAiClient(
            [
                {
                    "id": "resp_1",
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "call_1",
                            "name": "run_portal_analysis",
                            "arguments": (
                                '{"route":"analysis_request","analysis_type":"trend"}'
                            ),
                        }
                    ],
                },
                {
                    "id": "resp_2",
                    "output_text": "추세 분석을 완료했고 매출이 증가하고 있어요.",
                },
            ]
        ),
        dataset_service=FakeDatasetService(),
        analysis_service=analysis_service,
    )

    result = graph.invoke(
        {
            "session_id": "session-1",
            "message": "매출 추세를 분석해줘",
            "dataset_ids": ["dataset-1"],
            "session_dataset_ids": [],
        }
    )

    assert result["assistant_message"] == "추세 분석을 완료했고 매출이 증가하고 있어요."
    assert result["route"] == "analysis_request"
    assert result["analysis_type"] == "trend"
    assert result["analytics"] is not None
    assert result["workspace"] is not None
    assert analysis_service.calls[0].analysis_type == "trend"


def test_agent_graph_returns_state_when_no_final_message_is_present() -> None:
    graph = Agent(
        llm_client=FakeAiClient([{"id": "resp_1", "output": []}]),
        dataset_service=FakeDatasetService(),
        analysis_service=FakeAnalysisService(),
    )

    result = graph.invoke(
        {
            "session_id": "session-1",
            "message": "파일 분석해줘",
            "dataset_ids": ["dataset-1"],
            "session_dataset_ids": [],
        }
    )

    assert result["route"] == "conversation"
    assert "assistant_message" not in result


def test_agent_graph_allows_update_plan_tool() -> None:
    llm_client = FakeAiClient(
        [
            {
                "id": "resp_1",
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "update_plan",
                        "arguments": (
                            '{"explanation":"분석 전에 단계 정리","plan":[{"step":"데이터셋 확인","status":"completed"},{"step":"추세 분석 실행","status":"in_progress"}]}'
                        ),
                    }
                ],
            },
            {
                "id": "resp_2",
                "output_text": "먼저 데이터셋을 확인했고, 이제 추세 분석을 진행하겠습니다.",
            },
        ]
    )
    graph = Agent(
        llm_client=llm_client,
        dataset_service=FakeDatasetService(),
        analysis_service=FakeAnalysisService(),
    )

    result = graph.invoke(
        {
            "session_id": "session-1",
            "message": "분석 순서를 정리해줘",
            "dataset_ids": ["dataset-1"],
            "session_dataset_ids": [],
        }
    )

    assert (
        result["assistant_message"]
        == "먼저 데이터셋을 확인했고, 이제 추세 분석을 진행하겠습니다."
    )
    assert result["used_tools"] == ["update_plan"]
    assert result["plan_explanation"] == "분석 전에 단계 정리"
    assert result["plan"] == [
        {"step": "데이터셋 확인", "status": "completed"},
        {"step": "추세 분석 실행", "status": "in_progress"},
    ]


def test_agent_graph_parses_stream_events_and_executes_tool() -> None:
    first_stream = FakeStream(
        [
            {
                "type": "response.output_item.added",
                "item": {
                    "type": "function_call",
                    "call_id": "call_1",
                    "name": "inspect_dataset_context",
                },
            },
            {
                "type": "response.function_call_arguments.delta",
                "call_id": "call_1",
                "delta": '{"include_preview":true,"include_profile":true}',
            },
            {"type": "response.created", "response": {"id": "resp_1"}},
        ]
    )
    second_stream = FakeStream(
        [
            {"type": "response.created", "response": {"id": "resp_2"}},
            {
                "type": "response.output_text.delta",
                "delta": "데이터셋은 12행 2열이고 ",
            },
            {
                "type": "response.output_text.done",
                "text": "데이터셋은 12행 2열이고 sales 컬럼이 있습니다.",
            },
        ]
    )
    llm_client = FakeAiClient([first_stream, second_stream])
    graph = Agent(
        llm_client=llm_client,
        dataset_service=FakeDatasetService(),
        analysis_service=FakeAnalysisService(),
    )

    result = graph.invoke(
        {
            "session_id": "session-1",
            "message": "업로드된 데이터 컬럼을 설명해줘",
            "dataset_ids": [],
            "session_dataset_ids": ["dataset-1"],
        }
    )

    assert (
        result["assistant_message"]
        == "데이터셋은 12행 2열이고 sales 컬럼이 있습니다."
    )
    assert result["route"] == "dataset_analysis"
    assert result["used_tools"] == ["inspect_dataset_context"]
    assert first_stream.closed is True
    assert second_stream.closed is True


def test_agent_graph_stream_invoke_yields_output_text_deltas() -> None:
    llm_client = FakeAiClient(
        [
            FakeStream(
                [
                    {"type": "response.created", "response": {"id": "resp_1"}},
                    {"type": "response.output_text.delta", "delta": "안녕"},
                    {"type": "response.output_text.delta", "delta": "하세요"},
                    {
                        "type": "response.output_text.done",
                        "text": "안녕하세요",
                    },
                ]
            )
        ]
    )
    graph = Agent(
        llm_client=llm_client,
        dataset_service=FakeDatasetService(),
        analysis_service=FakeAnalysisService(),
    )

    stream = graph.stream_invoke(
        {
            "session_id": "session-1",
            "message": "인사해줘",
            "dataset_ids": [],
            "session_dataset_ids": [],
        }
    )

    events: list[dict[str, object]] = []
    try:
        while True:
            events.append(next(stream))
    except StopIteration as stop:
        result = stop.value

    assert events == [
        {
            "type": "response.output_text.delta",
            "delta": "안녕",
            "response_id": "resp_1",
        },
        {
            "type": "response.output_text.delta",
            "delta": "하세요",
            "response_id": "resp_1",
        },
    ]
    assert result["assistant_message"] == "안녕하세요"


def test_agent_graph_stream_invoke_yields_function_call_argument_sub_messages() -> None:
    llm_client = FakeAiClient(
        [
            FakeStream(
                [
                    {
                        "type": "response.output_item.added",
                        "item": {
                            "type": "function_call",
                            "call_id": "call_1",
                            "name": "inspect_dataset_context",
                        },
                    },
                    {
                        "type": "response.function_call_arguments.delta",
                        "call_id": "call_1",
                        "delta": '{"include_preview":',
                    },
                    {
                        "type": "response.function_call_arguments.done",
                        "call_id": "call_1",
                        "arguments": '{"include_preview":true}',
                    },
                    {"type": "response.created", "response": {"id": "resp_1"}},
                ]
            ),
            FakeStream(
                [
                    {"type": "response.created", "response": {"id": "resp_2"}},
                    {
                        "type": "response.output_text.done",
                        "text": "컨텍스트를 확인했습니다.",
                    },
                ]
            ),
        ]
    )
    graph = Agent(
        llm_client=llm_client,
        dataset_service=FakeDatasetService(),
        analysis_service=FakeAnalysisService(),
    )

    stream = graph.stream_invoke(
        {
            "session_id": "session-1",
            "message": "데이터셋 확인해줘",
            "dataset_ids": ["dataset-1"],
            "session_dataset_ids": [],
        }
    )

    events: list[dict[str, object]] = []
    try:
        while True:
            events.append(next(stream))
    except StopIteration as stop:
        result = stop.value

    assert events[0]["type"] == "agent.state"
    assert events[0]["state"]["route"] == "dataset_analysis"
    assert events[0]["state"]["used_tools"] == ["inspect_dataset_context"]
    assert events[0]["state"]["status"] == "profiling"
    assert result["assistant_message"] == "컨텍스트를 확인했습니다."


def test_agent_graph_stream_invoke_emits_state_after_tool_execution() -> None:
    llm_client = FakeAiClient(
        [
            FakeStream(
                [
                    {
                        "type": "response.output_item.added",
                        "item": {
                            "type": "function_call",
                            "call_id": "call_1",
                            "name": "run_portal_analysis",
                        },
                    },
                    {
                        "type": "response.function_call_arguments.done",
                        "call_id": "call_1",
                        "arguments": '{"route":"analysis_request","analysis_type":"trend"}',
                    },
                    {"type": "response.created", "response": {"id": "resp_1"}},
                ]
            ),
            FakeStream(
                [
                    {"type": "response.created", "response": {"id": "resp_2"}},
                    {
                        "type": "response.output_text.done",
                        "text": "추세 분석을 완료했습니다.",
                    },
                ]
            ),
        ]
    )
    graph = Agent(
        llm_client=llm_client,
        dataset_service=FakeDatasetService(),
        analysis_service=FakeAnalysisService(),
    )

    stream = graph.stream_invoke(
        {
            "session_id": "session-1",
            "message": "매출 추세를 분석해줘",
            "dataset_ids": ["dataset-1"],
            "session_dataset_ids": [],
        }
    )

    events: list[dict[str, object]] = []
    try:
        while True:
            events.append(next(stream))
    except StopIteration as stop:
        result = stop.value

    assert events[0]["type"] == "agent.state"
    assert events[0]["state"]["route"] == "analysis_request"
    assert events[0]["state"]["used_tools"] == ["run_portal_analysis"]
    assert events[0]["state"]["status"] == "running_analysis"
    assert events[0]["state"]["analytics"] is not None
    assert result["assistant_message"] == "추세 분석을 완료했습니다."


def test_agent_graph_stream_invoke_emits_plan_state_on_update_plan_output_item_done() -> None:
    llm_client = FakeAiClient(
        [
            FakeStream(
                [
                    {
                        "type": "response.output_item.done",
                        "item": {
                            "type": "function_call",
                            "call_id": "call_1",
                            "name": "update_plan",
                            "arguments": (
                                '{"explanation":"분석 전에 단계 정리","plan":[{"step":"데이터셋 확인","status":"completed"},{"step":"추세 분석 실행","status":"in_progress"}]}'
                            ),
                        },
                    },
                    {"type": "response.created", "response": {"id": "resp_1"}},
                ]
            ),
            FakeStream(
                [
                    {"type": "response.created", "response": {"id": "resp_2"}},
                    {
                        "type": "response.output_text.done",
                        "text": "먼저 데이터셋을 확인했고, 이제 추세 분석을 진행하겠습니다.",
                    },
                ]
            ),
        ]
    )
    graph = Agent(
        llm_client=llm_client,
        dataset_service=FakeDatasetService(),
        analysis_service=FakeAnalysisService(),
    )

    stream = graph.stream_invoke(
        {
            "session_id": "session-1",
            "message": "분석 순서를 정리해줘",
            "dataset_ids": ["dataset-1"],
            "session_dataset_ids": [],
        }
    )

    events: list[dict[str, object]] = []
    try:
        while True:
            events.append(next(stream))
    except StopIteration as stop:
        result = stop.value

    assert events[0]["type"] == "agent.state"
    assert events[0]["state"]["plan_explanation"] == "분석 전에 단계 정리"
    assert events[0]["state"]["plan"] == [
        {"step": "데이터셋 확인", "status": "completed"},
        {"step": "추세 분석 실행", "status": "in_progress"},
    ]
    assert result["assistant_message"] == "먼저 데이터셋을 확인했고, 이제 추세 분석을 진행하겠습니다."
