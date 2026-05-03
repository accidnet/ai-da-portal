from functools import lru_cache

from tools.dto import (
    DatasetInspectionData,
    DatasetInspectionPayload,
    ToolExecutionError,
    ToolExecutionResult,
)
from core.utils import read_string
from application.datasets.ports import DatasetMetadataReader
from application.datasets.tool_usecases import InspectDatasetContextUseCase
from infrastructure.db.repositories import DatasetRepository


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
                    "type": ["string", "array"],
                    "items": {"type": "string"},
                    "description": "프로파일과 미리보기를 확인할 특정 데이터셋 ID 또는 데이터셋 ID 배열입니다.",
                },
            },
            "required": ["dataset_id"],
            "additionalProperties": False,
        },
    }


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 선택 데이터셋의 context를 조회합니다."""
    dataset_ids = _read_dataset_ids(arguments.get("dataset_id"))
    if not dataset_ids:
        return ToolExecutionResult[DatasetInspectionData](
            ok=False,
            error="dataset_id is required.",
        ).model_dump(mode="json", exclude_none=True)

    datasets: list[DatasetInspectionPayload] = []
    errors: list[ToolExecutionError] = []
    for dataset_id in dataset_ids:
        try:
            datasets.append(_get_usecase().execute(dataset_id))
        except KeyError:
            errors.append(
                ToolExecutionError(
                    target_id=dataset_id,
                    message="Dataset not found.",
                )
            )
        except ValueError as exc:
            errors.append(ToolExecutionError(target_id=dataset_id, message=str(exc)))

    data = DatasetInspectionData(
        dataset_ids=dataset_ids,
        datasets=datasets,
    )
    if len(dataset_ids) == 1 and datasets and not errors:
        # 기존 단일 dataset 호출 소비자가 바로 읽을 수 있도록 최상위 필드도 유지합니다.
        data.dataset_id = datasets[0].dataset_id
        data.profile = datasets[0].profile
        data.preview = datasets[0].preview
    result = ToolExecutionResult[DatasetInspectionData](
        ok=not errors,
        data=data,
        errors=errors,
    )
    return result.model_dump(mode="json", exclude_none=True)


@lru_cache
def _get_usecase() -> InspectDatasetContextUseCase:
    """tool 실행 시 사용할 데이터셋 context usecase를 생성합니다."""
    # tool adapter는 application port와 infrastructure 구현체를 연결하는 composition 역할만 합니다.
    return InspectDatasetContextUseCase(dataset_reader=DatasetRepository())


def _read_dataset_ids(value: object) -> list[str]:
    """문자열 또는 문자열 배열 형태의 dataset_id argument를 정규화합니다."""
    if isinstance(value, list):
        values = [read_string(item) for item in value]
    else:
        values = [read_string(value)]

    dataset_ids: list[str] = []
    for dataset_id in values:
        if dataset_id is None or dataset_id in dataset_ids:
            continue
        dataset_ids.append(dataset_id)
    return dataset_ids
