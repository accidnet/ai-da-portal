from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_workspace_usecase
from features.workspaces.api.schemas import (
    WorkspaceCreateRequest,
    WorkspaceDeleteResponse,
    WorkspaceResponse,
    WorkspaceUpdateRequest,
)
from features.workspaces.application.dto import (
    WorkspaceCreateCommand,
    WorkspaceDeleteResult,
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
