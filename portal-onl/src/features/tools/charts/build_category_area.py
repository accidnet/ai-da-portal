from features.tools.charts.common import (
    build_trend_chart,
    load_dataframe_from_arguments,
    tool_error,
    tool_success,
)


def tool_definition() -> dict[str, object]:
    """category area chart 생성 tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "build_category_area",
        "description": "시간 흐름, 누적량, 총량 변화에 적합한 area chart payload를 생성합니다.",
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
    """LLM function_call arguments만 받아 category area chart를 생성합니다."""
    try:
        dataset_id, dataframe = load_dataframe_from_arguments(arguments)
        chart = build_trend_chart(
            dataframe,
            chart_id="category_area",
            chart_type="area",
        )
    except KeyError:
        return tool_error("Dataset not found.")
    except ValueError as exc:
        return tool_error(str(exc))
    return tool_success({"dataset_id": dataset_id, "chart": chart.model_dump(mode="json")})
