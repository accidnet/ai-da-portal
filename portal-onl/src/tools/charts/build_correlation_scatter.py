from tools.charts.common import (
    build_correlation_scatter,
    load_dataframe_from_arguments,
    tool_error,
    tool_success,
)


def tool_definition() -> dict[str, object]:
    """correlation scatter chart 생성 tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "build_correlation_scatter",
        "description": "처음 두 숫자형 컬럼으로 correlation scatter chart payload를 생성합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "대상 데이터셋 ID입니다."}
            },
            "required": ["dataset_id"],
            "additionalProperties": False,
        },
    }


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 correlation scatter chart를 생성합니다."""
    try:
        dataset_id, dataframe = load_dataframe_from_arguments(arguments)
        chart = build_correlation_scatter(dataframe)
    except KeyError:
        return tool_error("Dataset not found.")
    except ValueError as exc:
        return tool_error(str(exc))
    return tool_success({"dataset_id": dataset_id, "chart": chart.model_dump(mode="json")})
