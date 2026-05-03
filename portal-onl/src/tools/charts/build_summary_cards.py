from tools.charts.common import (
    build_summary_cards,
    load_dataframe_from_arguments,
    tool_error,
    tool_success,
)


def tool_definition() -> dict[str, object]:
    """summary cards 생성 tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "build_summary_cards",
        "description": "데이터셋의 행/열 수, 숫자형 컬럼 수, 결측 셀 수 summary cards를 생성합니다.",
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
    """LLM function_call arguments만 받아 summary cards를 생성합니다."""
    try:
        dataset_id, dataframe = load_dataframe_from_arguments(arguments)
        cards = [card.model_dump(mode="json") for card in build_summary_cards(dataframe)]
    except KeyError:
        return tool_error("Dataset not found.")
    except ValueError as exc:
        return tool_error(str(exc))
    return tool_success({"dataset_id": dataset_id, "summary_cards": cards})
