from tools.charts.common import (
    build_analytics,
    load_dataframe_from_arguments,
    read_analysis_type,
    read_prompt,
    tool_error,
    tool_success,
)


def tool_definition() -> dict[str, object]:
    """전체 analytics payload 생성 tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "build_chart_analytics",
        "description": "데이터셋에서 summary cards, chart, table, insight, profile을 한 번에 생성합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "대상 데이터셋 ID입니다."},
                "analysis_type": {"type": "string", "description": "분석 유형입니다."},
                "prompt": {"type": ["string", "null"], "description": "선택적 사용자 질문입니다."},
            },
            "required": ["dataset_id", "analysis_type"],
            "additionalProperties": False,
        },
    }


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 analytics payload를 생성합니다."""
    try:
        dataset_id, dataframe = load_dataframe_from_arguments(arguments)
        payload = build_analytics(
            dataframe,
            analysis_type=read_analysis_type(arguments),
            prompt=read_prompt(arguments),
        )
    except KeyError:
        return tool_error("Dataset not found.")
    except ValueError as exc:
        return tool_error(str(exc))

    return tool_success(
        {"dataset_id": dataset_id, "analytics": payload.model_dump(mode="json")}
    )
