from fastapi import APIRouter, Depends, status

from api.deps import get_session_service
from domain.sessions.schemas import (
    SessionCreateRequest,
    SessionDetail,
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
    return service.get(session_id)
