from core.utils import read_string
from features.data_sources.domain.models import DataSourceItem
from features.data_sources.infrastructure.repositories import DataSourceRepository
from features.tools.dto import ToolExecutionError, ToolExecutionResult
from infrastructure.db.repositories import DatasetRepository
from infrastructure.db.repositories.dataset_repository import (
    DatasetRecord,
    DatasetSourceRecord,
)


def tool_definition() -> dict[str, object]:
    """dataset_id 기준 DB 저장 정보를 조회하는 agent tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "get_dataset_info",
        "description": (
            "dataset_id에 해당하는 데이터셋 DB 메타데이터와 연결된 원천 데이터 파일 경로를 조회합니다. "
            "CLI로 데이터 파일을 다루기 전에 실제 파일 path가 필요할 때 사용합니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": ["string", "array"],
                    "items": {"type": "string"},
                    "description": "조회할 데이터셋 ID 또는 데이터셋 ID 배열입니다.",
                },
            },
            "required": ["dataset_id"],
            "additionalProperties": False,
        },
    }


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 데이터셋 DB 정보를 조회합니다."""
    dataset_ids = _read_dataset_ids(arguments.get("dataset_id"))
    if not dataset_ids:
        return ToolExecutionResult[object](
            ok=False,
            error="dataset_id is required.",
        ).model_dump(mode="json", exclude_none=True)

    repository = DatasetRepository()
    datasets: list[dict[str, object]] = []
    errors: list[ToolExecutionError] = []
    for dataset_id in dataset_ids:
        try:
            dataset = repository.get_or_raise(dataset_id)
        except KeyError:
            errors.append(
                ToolExecutionError(
                    target_id=dataset_id,
                    message="Dataset not found.",
                )
            )
            continue
        source_items = _load_source_items(dataset)
        datasets.append(_build_dataset_info(dataset, source_items))

    data = {
        "dataset_ids": dataset_ids,
        "datasets": datasets,
    }
    if len(dataset_ids) == 1 and datasets and not errors:
        data.update(datasets[0])
    return ToolExecutionResult[dict[str, object]](
        ok=not errors,
        data=data,
        errors=errors,
    ).model_dump(mode="json", exclude_none=True)


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


def _load_source_items(dataset: DatasetRecord) -> dict[str, DataSourceItem]:
    """데이터셋 source_ref_id에 연결된 원천 데이터 노드를 한 번에 조회합니다."""
    source_ref_ids = [
        source.source_ref_id
        for source in dataset.sources
        if source.source_ref_id is not None
    ]
    if not source_ref_ids:
        return {}

    items = DataSourceRepository().list_items_by_ids(list(dict.fromkeys(source_ref_ids)))
    return {item.id: item for item in items}


def _build_dataset_info(
    dataset: DatasetRecord,
    source_items: dict[str, DataSourceItem],
) -> dict[str, object]:
    """데이터셋 record와 원천 데이터 record를 tool 응답 payload로 변환합니다."""
    files = [
        _build_file_info(source, source_items)
        for source in dataset.sources
    ]
    return {
        "dataset_id": dataset.id,
        "name": dataset.name,
        "description": dataset.description,
        "created_at": dataset.created_at.isoformat(),
        "updated_at": dataset.updated_at.isoformat(),
        "file_count": len(files),
        "files": files,
        "sources": files,
    }


def _build_file_info(
    source: DatasetSourceRecord,
    source_items: dict[str, DataSourceItem],
) -> dict[str, object]:
    """단일 dataset source에 파일 단위 DB row와 원천 파일 path 정보를 합칩니다."""
    source_item = (
        source_items.get(source.source_ref_id)
        if source.source_ref_id is not None
        else None
    )
    return {
        "dataset_source_id": source.id,
        "file_id": source.source_ref_id,
        "source_ref_id": source.source_ref_id,
        "row_count": source.row_count,
        "column_count": source.column_count,
        "created_at": source.created_at.isoformat(),
        # CLI 접근 가능성을 판단해야 하므로 path 키는 항상 포함합니다.
        "path": source_item.storage_path if source_item is not None else None,
        "relative_path": source_item.relative_path if source_item is not None else None,
        "source_name": source_item.name if source_item is not None else None,
        "source_type": source_item.item_type if source_item is not None else None,
        "content_type": source_item.content_type if source_item is not None else None,
        "size_bytes": source_item.size_bytes if source_item is not None else None,
    }
