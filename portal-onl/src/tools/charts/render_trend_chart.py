from shared.integrations.ai.contracts import Function
from tools.charts.common import (
    build_correlation_scatter,
    load_dataframe_from_arguments,
    tool_error,
    tool_success,
)


def tool_definition() -> dict[str, object]:
    """trend chart 생성 tool 정의를 반환합니다."""
    definition = Function(
        name="render_trend_chart",
        description="숫자형 컬럼과 날짜/index 축으로 line 또는 area trend chart payload를 생성합니다.",
        parameters={
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "string",
                    "description": "대상 데이터셋 ID입니다.",
                },
                "chart_id": {
                    "type": "string",
                    "enum": ["trend_line", "category_area"],
                    "description": "생성할 trend chart id입니다.",
                },
                "chart_type": {
                    "type": "string",
                    "enum": ["line", "area"],
                    "description": "렌더링 chart type입니다.",
                },
            },
            "required": ["dataset_id"],
            "additionalProperties": False,
        },
    )
    return definition.model_dump(mode="json", exclude_none=True)


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 correlation scatter chart를 생성합니다."""
    try:
        dataset_id, dataframe = load_dataframe_from_arguments(arguments)
        chart = build_correlation_scatter(dataframe)
    except KeyError:
        return tool_error("Dataset not found.")
    except ValueError as exc:
        return tool_error(str(exc))
    return tool_success(
        {"dataset_id": dataset_id, "chart": chart.model_dump(mode="json")}
    )
