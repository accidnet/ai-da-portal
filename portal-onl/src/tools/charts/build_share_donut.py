from tools.charts.common import (
    build_share_donut,
    load_dataframe_from_arguments,
    tool_error,
    tool_success,
)


def tool_definition() -> dict[str, object]:
    """share donut chart 생성 tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "build_share_donut",
        "description": "범주형 컬럼별 숫자 합계 비중을 donut chart payload로 생성합니다.",
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
    """LLM function_call arguments만 받아 share donut chart를 생성합니다."""
    try:
        dataset_id, dataframe = load_dataframe_from_arguments(arguments)
        chart = build_share_donut(dataframe)
    except KeyError:
        return tool_error("Dataset not found.")
    except ValueError as exc:
        return tool_error(str(exc))
    return tool_success({"dataset_id": dataset_id, "chart": chart.model_dump(mode="json")})
