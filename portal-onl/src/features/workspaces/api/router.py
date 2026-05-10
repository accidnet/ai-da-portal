from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_workspace_usecase
from features.workspaces.api.schemas import (
    WorkspaceCreateRequest,
    WorkspaceResponse,
)
from features.workspaces.application.usecase import WorkspaceUsecase

router = APIRouter()


@router.get("", response_model=list[WorkspaceResponse])
def list_workspaces(
    usecase: WorkspaceUsecase = Depends(get_workspace_usecase),
) -> list[WorkspaceResponse]:
    """저장된 워크스페이스 목록을 조회합니다."""
    return usecase.list_workspaces()


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreateRequest,
    usecase: WorkspaceUsecase = Depends(get_workspace_usecase),
) -> WorkspaceResponse:
    """워크스페이스 이름을 받아 새 워크스페이스를 생성합니다."""
    try:
        return usecase.create(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
