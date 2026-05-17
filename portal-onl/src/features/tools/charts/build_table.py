from features.tools.charts.common import (
    build_table,
    load_dataframe_from_arguments,
    read_analysis_type,
    tool_error,
    tool_success,
)


def tool_definition() -> dict[str, object]:
    """table payload 생성 tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "build_table",
        "description": "분석 유형에 맞는 table payload를 생성합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "대상 데이터셋 ID입니다."},
                "analysis_type": {"type": "string", "description": "분석 유형입니다."},
            },
            "required": ["dataset_id", "analysis_type"],
            "additionalProperties": False,
        },
    }


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 table payload를 생성합니다."""
    try:
        dataset_id, dataframe = load_dataframe_from_arguments(arguments)
        table = build_table(dataframe, analysis_type=read_analysis_type(arguments))
    except KeyError:
        return tool_error("Dataset not found.")
    except ValueError as exc:
        return tool_error(str(exc))
    return tool_success({"dataset_id": dataset_id, "table": table.model_dump(mode="json")})
