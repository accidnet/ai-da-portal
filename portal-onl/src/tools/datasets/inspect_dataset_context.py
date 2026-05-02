from collections.abc import Callable

from agents.state import AgentState


type DatasetIdResolver = Callable[[AgentState, str | None], str | None]
type DatasetIdsProvider = Callable[[AgentState], list[str]]
type StringReader = Callable[[object], str | None]
type BoolReader = Callable[[object, bool], bool]


def tool_definition() -> dict[str, object]:
    """데이터셋 구조 확인용 에이전트 tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "inspect_dataset_context",
        "description": (
            "업로드된 데이터의 구조, 컬럼, 품질, 범위, 사용 가능한 행에 대한 질문에 답하기 전에 데이터셋 프로필과 미리보기를 확인합니다. 상관관계나 추세 분석 같은 실제 분석 결론에는 이 함수를 사용하지 마세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": ["string", "null"],
                    "description": "확인할 특정 데이터셋 ID입니다. null이면 현재 사용할 수 있는 가장 적절한 데이터셋을 확인합니다.",
                },
                "include_preview": {
                    "type": "boolean",
                    "description": "표 형태의 미리보기 행을 포함할지 여부입니다.",
                    "default": True,
                },
                "include_profile": {
                    "type": "boolean",
                    "description": "데이터셋 프로파일 통계를 포함할지 여부입니다.",
                    "default": True,
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    }


def execute(
    state: AgentState,
    arguments: dict[str, object],
    *,
    dataset_service,
    resolve_dataset_id: DatasetIdResolver,
    available_dataset_ids: DatasetIdsProvider,
    read_string: StringReader,
    read_bool: BoolReader,
) -> dict[str, object]:
    """선택된 데이터셋의 profile과 preview를 조회합니다."""
    state["route"] = "dataset_analysis"
    state["status"] = "profiling"

    dataset_id = resolve_dataset_id(state, read_string(arguments.get("dataset_id")))
    if dataset_id is None:
        return {
            "ok": False,
            "error": "No dataset is available.",
            "available_dataset_ids": available_dataset_ids(state),
        }

    include_preview = read_bool(arguments.get("include_preview"), True)
    include_profile = read_bool(arguments.get("include_profile"), True)
    payload: dict[str, object] = {
        "ok": True,
        "dataset_id": dataset_id,
        "available_dataset_ids": available_dataset_ids(state),
    }
    if include_profile:
        payload["profile"] = dataset_service.get_profile(dataset_id).model_dump(
            mode="json"
        )
    if include_preview:
        payload["preview"] = dataset_service.get_preview(dataset_id).model_dump(
            mode="json"
        )
    state["resolved_dataset_id"] = dataset_id
    return payload
