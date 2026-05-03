from tools.charts.common import (
    load_dataframe_from_arguments,
    read_analysis_type,
    read_prompt,
    select_chart_spec,
    tool_error,
    tool_success,
)


def tool_definition() -> dict[str, object]:
    """chart spec 선택 tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "select_chart_spec",
        "description": "데이터셋 컬럼 타입과 분석 유형에 맞는 chart id/type을 선택합니다.",
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
    """LLM function_call arguments만 받아 chart spec을 선택합니다."""
    try:
        dataset_id, dataframe = load_dataframe_from_arguments(arguments)
        spec = select_chart_spec(
            dataframe,
            analysis_type=read_analysis_type(arguments),
            prompt=read_prompt(arguments),
        )
    except KeyError:
        return tool_error("Dataset not found.")
    except ValueError as exc:
        return tool_error(str(exc))
    return tool_success({"dataset_id": dataset_id, "chart_spec": {"id": spec.id, "type": spec.type}})
