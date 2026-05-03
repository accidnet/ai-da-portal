from tools.charts.common import (
    inspect_columns,
    load_dataframe_from_arguments,
    tool_error,
    tool_success,
)


def tool_definition() -> dict[str, object]:
    """chart 컬럼 타입 분류 tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "inspect_chart_columns",
        "description": "chart 생성에 사용할 숫자형, 날짜형, 범주형 컬럼 목록을 분류합니다.",
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
    """LLM function_call arguments만 받아 chart 컬럼 타입을 분류합니다."""
    try:
        dataset_id, dataframe = load_dataframe_from_arguments(arguments)
        columns = inspect_columns(dataframe)
    except KeyError:
        return tool_error("Dataset not found.")
    except ValueError as exc:
        return tool_error(str(exc))
    return tool_success({"dataset_id": dataset_id, **columns})
