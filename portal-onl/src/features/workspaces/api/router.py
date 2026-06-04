from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_dataset_service, get_workspace_usecase
from features.datasets.application.service import DatasetApplicationService
from features.workspaces.api.schemas import (
    WorkspaceCreateRequest,
    WorkspaceDatasetLinkRequest,
    WorkspaceDatasetLinkResponse,
    WorkspaceDeleteResponse,
    WorkspaceFileContentResponse,
    WorkspaceFileEntryResponse,
    WorkspaceFileListResponse,
    WorkspaceResponse,
    WorkspaceUpdateRequest,
)
from features.workspaces.application.dto import (
    WorkspaceCreateCommand,
    WorkspaceDatasetLinkResult,
    WorkspaceDeleteResult,
    WorkspaceFileContentResult,
    WorkspaceFileEntryResult,
    WorkspaceFileListResult,
    WorkspaceResult,
    WorkspaceUpdateCommand,
)
from features.workspaces.application.usecase import WorkspaceUsecase

router = APIRouter()


@router.get("", response_model=list[WorkspaceResponse])
def list_workspaces(
    usecase: WorkspaceUsecase = Depends(get_workspace_usecase),
) -> list[WorkspaceResponse]:
    """저장된 워크스페이스 목록을 조회합니다."""
    return [_to_workspace_response(workspace) for workspace in usecase.list_workspaces()]


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreateRequest,
    usecase: WorkspaceUsecase = Depends(get_workspace_usecase),
) -> WorkspaceResponse:
    """워크스페이스 이름을 받아 새 워크스페이스를 생성합니다."""
    try:
        return _to_workspace_response(
            usecase.create(WorkspaceCreateCommand(name=payload.name))
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
def update_workspace(
    workspace_id: str,
    payload: WorkspaceUpdateRequest,
    usecase: WorkspaceUsecase = Depends(get_workspace_usecase),
) -> WorkspaceResponse:
    """워크스페이스 이름을 수정합니다."""
    try:
        return _to_workspace_response(
            usecase.update(workspace_id, WorkspaceUpdateCommand(name=payload.name))
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete("/{workspace_id}", response_model=WorkspaceDeleteResponse)
def delete_workspace(
    workspace_id: str,
    usecase: WorkspaceUsecase = Depends(get_workspace_usecase),
) -> WorkspaceDeleteResponse:
    """워크스페이스를 삭제합니다."""
    try:
        return _to_workspace_delete_response(usecase.delete(workspace_id))
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' was not found.",
        ) from exc


@router.get("/{workspace_id}/files", response_model=WorkspaceFileListResponse)
def list_workspace_files(
    workspace_id: str,
    path: str | None = None,
    max_entries: int | None = None,
    usecase: WorkspaceUsecase = Depends(get_workspace_usecase),
) -> WorkspaceFileListResponse:
    """워크스페이스 로컬 저장소의 현재 폴더 항목을 조회합니다."""
    try:
        return _to_workspace_file_list_response(
            usecase.list_files(
                workspace_id=workspace_id,
                path=path,
                max_entries=max_entries,
            )
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' was not found.",
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace path was not found.",
        ) from exc
    except (NotADirectoryError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/{workspace_id}/files/content", response_model=WorkspaceFileContentResponse)
def read_workspace_file(
    workspace_id: str,
    path: str,
    max_bytes: int | None = None,
    usecase: WorkspaceUsecase = Depends(get_workspace_usecase),
) -> WorkspaceFileContentResponse:
    """워크스페이스 로컬 저장소의 텍스트 파일 내용을 조회합니다."""
    try:
        return _to_workspace_file_content_response(
            usecase.read_file(
                workspace_id=workspace_id,
                path=path,
                max_bytes=max_bytes,
            )
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' was not found.",
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace file was not found.",
        ) from exc
    except (IsADirectoryError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/{workspace_id}/datasets",
    response_model=WorkspaceDatasetLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
def attach_workspace_dataset(
    workspace_id: str,
    payload: WorkspaceDatasetLinkRequest,
    usecase: WorkspaceUsecase = Depends(get_workspace_usecase),
    dataset_service: DatasetApplicationService = Depends(get_dataset_service),
) -> WorkspaceDatasetLinkResponse:
    """워크스페이스에 데이터셋을 연결합니다."""
    try:
        dataset_service.get(payload.dataset_id)
        return _to_workspace_dataset_link_response(
            usecase.attach_dataset(
                workspace_id=workspace_id,
                dataset_id=payload.dataset_id,
            )
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace or dataset was not found.",
        ) from exc


@router.get(
    "/{workspace_id}/datasets",
    response_model=WorkspaceDatasetLinkResponse,
)
def list_workspace_datasets(
    workspace_id: str,
    usecase: WorkspaceUsecase = Depends(get_workspace_usecase),
) -> WorkspaceDatasetLinkResponse:
    """워크스페이스에 연결된 데이터셋 ID 목록을 반환합니다."""
    try:
        return _to_workspace_dataset_link_response(
            usecase.list_dataset_ids(workspace_id)
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' was not found.",
        ) from exc


@router.delete(
    "/{workspace_id}/datasets/{dataset_id}",
    response_model=WorkspaceDatasetLinkResponse,
)
def detach_workspace_dataset(
    workspace_id: str,
    dataset_id: str,
    usecase: WorkspaceUsecase = Depends(get_workspace_usecase),
    dataset_service: DatasetApplicationService = Depends(get_dataset_service),
) -> WorkspaceDatasetLinkResponse:
    """워크스페이스에서 데이터셋 연결을 해제합니다."""
    try:
        dataset_service.get(dataset_id)
        return _to_workspace_dataset_link_response(
            usecase.detach_dataset(workspace_id=workspace_id, dataset_id=dataset_id)
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace or dataset was not found.",
        ) from exc


def _to_workspace_response(workspace: WorkspaceResult) -> WorkspaceResponse:
    """application DTO를 API 응답 모델로 변환합니다."""
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
    )


def _to_workspace_delete_response(
    result: WorkspaceDeleteResult,
) -> WorkspaceDeleteResponse:
    """삭제 결과 DTO를 API 응답 모델로 변환합니다."""
    return WorkspaceDeleteResponse(id=result.id, deleted=result.deleted)


def _to_workspace_dataset_link_response(
    result: WorkspaceDatasetLinkResult,
) -> WorkspaceDatasetLinkResponse:
    """워크스페이스 데이터셋 연결 DTO를 API 응답 모델로 변환합니다."""
    return WorkspaceDatasetLinkResponse(
        workspace_id=result.workspace_id,
        dataset_ids=result.dataset_ids,
    )


def _to_workspace_file_list_response(
    result: WorkspaceFileListResult,
) -> WorkspaceFileListResponse:
    """파일 목록 DTO를 API 응답 모델로 변환합니다."""
    return WorkspaceFileListResponse(
        workspace_id=result.workspace_id,
        path=result.path,
        entries=[
            _to_workspace_file_entry_response(entry) for entry in result.entries
        ],
        has_more=result.has_more,
    )


def _to_workspace_file_entry_response(
    result: WorkspaceFileEntryResult,
) -> WorkspaceFileEntryResponse:
    """파일 항목 DTO를 API 응답 모델로 변환합니다."""
    return WorkspaceFileEntryResponse(
        path=result.path,
        name=result.name,
        kind=result.kind,
        size_bytes=result.size_bytes,
        updated_at=result.updated_at,
    )


def _to_workspace_file_content_response(
    result: WorkspaceFileContentResult,
) -> WorkspaceFileContentResponse:
    """파일 내용 DTO를 API 응답 모델로 변환합니다."""
    return WorkspaceFileContentResponse(
        workspace_id=result.workspace_id,
        path=result.path,
        name=result.name,
        size_bytes=result.size_bytes,
        content=result.content,
        is_binary=result.is_binary,
        truncated=result.truncated,
    )
