from fastapi import APIRouter, Depends, status
from fastapi import HTTPException

from api.deps import get_dataset_service, get_session_service
from domain.datasets.service import DatasetService
from domain.sessions.schemas import (
    SessionCreateRequest,
    SessionDetail,
    SessionSnapshotResponse,
    SessionSummary,
)
from domain.sessions.service import SessionService

router = APIRouter()


@router.post("", response_model=SessionDetail, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreateRequest,
    service: SessionService = Depends(get_session_service),
) -> SessionDetail:
    return service.create(payload)


@router.get("", response_model=list[SessionSummary])
def list_sessions(
    service: SessionService = Depends(get_session_service),
) -> list[SessionSummary]:
    return service.list_sessions()


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(
    session_id: str, service: SessionService = Depends(get_session_service)
) -> SessionDetail:
    try:
        return service.get(session_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' was not found.",
        ) from exc


@router.get("/{session_id}/snapshot", response_model=SessionSnapshotResponse)
def get_session_snapshot(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
    dataset_service: DatasetService = Depends(get_dataset_service),
) -> SessionSnapshotResponse:
    try:
        return session_service.get_snapshot(session_id, dataset_service)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' was not found.",
        ) from exc
