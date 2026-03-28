from fastapi import APIRouter, Depends, status
from fastapi import HTTPException

from api.deps import get_dataset_service, get_session_service
from domain.datasets.service import DatasetService
from domain.sessions.schemas import (
    SessionCreateRequest,
    SessionDatasetLinkRequest,
    SessionDatasetLinkResponse,
    SessionDeleteResponse,
    SessionDetail,
    SessionSnapshotResponse,
    SessionSummary,
    SessionUpdateRequest,
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
    dataset_service: DatasetService = Depends(get_dataset_service),
) -> list[SessionSummary]:
    return service.list_sessions(dataset_service)


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
    dataset_service: DatasetService = Depends(get_dataset_service),
) -> SessionDetail:
    try:
        return service.hydrate_session_detail(session_id, dataset_service)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' was not found.",
        ) from exc


@router.patch("/{session_id}", response_model=SessionDetail)
def update_session(
    session_id: str,
    payload: SessionUpdateRequest,
    service: SessionService = Depends(get_session_service),
    dataset_service: DatasetService = Depends(get_dataset_service),
) -> SessionDetail:
    try:
        service.update(session_id, payload)
        return service.hydrate_session_detail(session_id, dataset_service)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete("/{session_id}", response_model=SessionDeleteResponse)
def delete_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
) -> SessionDeleteResponse:
    try:
        return service.delete(session_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' was not found.",
        ) from exc


@router.post(
    "/{session_id}/datasets",
    response_model=SessionDatasetLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
def attach_session_dataset(
    session_id: str,
    payload: SessionDatasetLinkRequest,
    session_service: SessionService = Depends(get_session_service),
    dataset_service: DatasetService = Depends(get_dataset_service),
) -> SessionDatasetLinkResponse:
    try:
        dataset_service.get(payload.dataset_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{payload.dataset_id}' was not found.",
        ) from exc
    return session_service.attach_dataset(session_id, payload.dataset_id)


@router.delete(
    "/{session_id}/datasets/{dataset_id}",
    response_model=SessionDatasetLinkResponse,
)
def detach_session_dataset(
    session_id: str,
    dataset_id: str,
    session_service: SessionService = Depends(get_session_service),
    dataset_service: DatasetService = Depends(get_dataset_service),
) -> SessionDatasetLinkResponse:
    try:
        dataset_service.get(dataset_id)
        return session_service.detach_dataset(session_id, dataset_id)
    except KeyError as exc:
        try:
            session_service.get(session_id)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' was not found.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' was not found.",
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
