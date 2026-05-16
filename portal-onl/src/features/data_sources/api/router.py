from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from features.data_sources.api.deps import get_data_source_usecase
from features.data_sources.api.schemas import (
    DataSourceItemResponse,
    DataSourceDeleteResponse,
    DataSourceTreeResponse,
    DataSourceUploadResponse,
)
from features.data_sources.application.dto import (
    DataSourceItemResult,
    DataSourceDeleteResult,
    DataSourceUploadCommand,
    DataSourceUploadFile,
    DataSourceUploadResult,
)
from features.data_sources.application.usecase import DataSourceUsecase

router = APIRouter()


@router.post(
    "/uploads",
    response_model=DataSourceUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_data_sources(
    files: list[UploadFile] = File(...),
    relative_paths: list[str] | None = Form(default=None),
    usecase: DataSourceUsecase = Depends(get_data_source_usecase),
) -> DataSourceUploadResponse:
    """파일 여러 개 또는 폴더 선택 결과를 원천 데이터 저장소에 업로드합니다."""
    try:
        upload_files = [
            DataSourceUploadFile(
                filename=file.filename or "uploaded-file",
                content=await file.read(),
                content_type=file.content_type,
            )
            for file in files
        ]
        result = usecase.upload(
            DataSourceUploadCommand(
                files=upload_files,
                relative_paths=relative_paths or [],
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return _to_upload_response(result)


@router.get("/tree", response_model=DataSourceTreeResponse)
def list_data_source_tree(
    usecase: DataSourceUsecase = Depends(get_data_source_usecase),
) -> DataSourceTreeResponse:
    """DB에 저장된 flat 노드를 프론트 표시용 트리 구조로 반환합니다."""
    return DataSourceTreeResponse(items=_build_tree_response(usecase.list_items()))


@router.delete("/{item_id}", response_model=DataSourceDeleteResponse)
def delete_data_source_item(
    item_id: str,
    usecase: DataSourceUsecase = Depends(get_data_source_usecase),
) -> DataSourceDeleteResponse:
    """원천 데이터 파일 또는 폴더 노드를 삭제합니다."""
    try:
        return _to_delete_response(usecase.delete(item_id))
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source item '{item_id}' was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


def _to_upload_response(result: DataSourceUploadResult) -> DataSourceUploadResponse:
    """application 업로드 결과를 API 응답으로 변환합니다."""
    return DataSourceUploadResponse(items=_build_tree_response(result.items))


def _to_delete_response(result: DataSourceDeleteResult) -> DataSourceDeleteResponse:
    """application 삭제 결과를 API 응답으로 변환합니다."""
    return DataSourceDeleteResponse(
        id=result.id,
        deleted=result.deleted,
        deleted_count=result.deleted_count,
    )


def _to_item_response(item: DataSourceItemResult) -> DataSourceItemResponse:
    """application 파일/폴더 DTO를 API 응답으로 변환합니다."""
    return DataSourceItemResponse(
        id=item.id,
        parent_id=item.parent_id,
        item_type=item.item_type,
        name=item.name,
        relative_path=item.relative_path,
        depth=item.depth,
        sort_order=item.sort_order,
        content_type=item.content_type,
        size_bytes=item.size_bytes,
        storage_path=item.storage_path,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _build_tree_response(
    items: list[DataSourceItemResult],
) -> list[DataSourceItemResponse]:
    """parent_id 관계를 사용해 flat 노드를 트리 응답으로 조립합니다."""
    node_by_id = {item.id: _to_item_response(item) for item in items}
    roots: list[DataSourceItemResponse] = []

    for item in sorted(items, key=lambda item: (item.depth, item.sort_order, item.name)):
        node = node_by_id[item.id]
        if item.parent_id and item.parent_id in node_by_id:
            node_by_id[item.parent_id].children.append(node)
        else:
            roots.append(node)

    return roots
