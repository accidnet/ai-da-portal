from collections.abc import Callable
from typing import Literal, cast

from agents.state import AgentState
from domain.analyses.schemas import AnalysisRequest


type DatasetIdResolver = Callable[[AgentState, str | None], str | None]
type DatasetIdsProvider = Callable[[AgentState], list[str]]
type StringReader = Callable[[object], str | None]
type StringRequirer = Callable[[AgentState, str], str]


def tool_definition() -> dict[str, object]:
    return {
        "type": "function",
        "name": "run_portal_analysis",
        "description": (
            "백엔드 데이터셋 프로파일링 또는 분석을 실행하고 최종 답변에 사용할 구조화된 결과를 반환합니다. 업로드된 데이터의 계산 결과나 시각 요약에 근거해야 하는 답변에는 이 함수를 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "route": {
                    "type": "string",
                    "enum": ["dataset_analysis", "analysis_request"],
                    "description": "데이터셋 개요나 프로파일 작업에는 dataset_analysis를, 구체적인 분석 질문에는 analysis_request를 사용합니다.",
                },
                "analysis_type": {
                    "type": "string",
                    "enum": [
                        "dataset_profile",
                        "descriptive_summary",
                        "correlation",
                        "trend",
                        "grouped_aggregation",
                        "anomaly_detection",
                    ],
                    "description": "실행할 백엔드 분석 유형입니다.",
                },
                "dataset_id": {
                    "type": ["string", "null"],
                    "description": "분석할 특정 데이터셋 ID입니다. null이면 자동으로 결정합니다.",
                },
                "prompt": {
                    "type": ["string", "null"],
                    "description": "분석 요청을 위한 선택적 추가 지시문입니다.",
                },
            },
            "required": ["route", "analysis_type"],
            "additionalProperties": False,
        },
    }


def execute(
    state: AgentState,
    arguments: dict[str, object],
    *,
    dataset_service,
    analysis_service,
    resolve_dataset_id: DatasetIdResolver,
    available_dataset_ids: DatasetIdsProvider,
    read_string: StringReader,
    require_string: StringRequirer,
) -> dict[str, object]:
    state["status"] = "running_analysis"

    route = read_string(arguments.get("route")) or "analysis_request"
    analysis_type = read_string(arguments.get("analysis_type"))
    dataset_id = resolve_dataset_id(state, read_string(arguments.get("dataset_id")))
    if dataset_id is None:
        return {
            "ok": False,
            "route": route,
            "analysis_type": analysis_type,
            "error": "No dataset is available for analysis.",
            "available_dataset_ids": available_dataset_ids(state),
        }
    if analysis_type is None:
        return {
            "ok": False,
            "route": route,
            "error": "analysis_type is required.",
        }

    resolved_analysis_type = cast(
        Literal[
            "dataset_profile",
            "descriptive_summary",
            "correlation",
            "trend",
            "grouped_aggregation",
            "anomaly_detection",
        ],
        analysis_type,
    )
    prompt = read_string(arguments.get("prompt")) or require_string(state, "message")
    detail = analysis_service.create(
        AnalysisRequest(
            session_id=require_string(state, "session_id"),
            dataset_id=dataset_id,
            analysis_type=resolved_analysis_type,
            prompt=prompt,
        )
    )
    state["route"] = route  # type: ignore[assignment]
    state["analysis_type"] = analysis_type
    state["resolved_dataset_id"] = dataset_id
    state["analytics"] = detail.analytics
    state["workspace"] = detail.workspace

    analytics = detail.analytics
    workspace = detail.workspace
    return {
        "ok": True,
        "route": route,
        "analysis_type": analysis_type,
        "dataset_id": dataset_id,
        "analysis_id": detail.id,
        "summary_cards": (
            [card.model_dump(mode="json") for card in analytics.summary_cards[:4]]
            if analytics is not None
            else []
        ),
        "chart_titles": (
            [chart.title for chart in analytics.charts[:3]]
            if analytics is not None
            else []
        ),
        "table_titles": (
            [table.title for table in analytics.tables[:2]]
            if analytics is not None
            else []
        ),
        "insights": (
            [insight.model_dump(mode="json") for insight in analytics.insights[:3]]
            if analytics is not None
            else []
        ),
        "workspace": workspace.model_dump(mode="json") if workspace else None,
    }
