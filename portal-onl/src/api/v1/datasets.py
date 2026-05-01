from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from api.deps import get_dataset_service, get_session_service
from domain.datasets.schemas import (
    DatasetDeleteResponse,
    DatasetInfo,
    DatasetPreviewResponse,
    DatasetProfileResponse,
    DatasetSummary,
)
from domain.datasets.service import DatasetService
from domain.sessions.service import SessionService

router = APIRouter()


@router.get("", response_model=list[DatasetSummary])
def list_datasets(
    service: DatasetService = Depends(get_dataset_service),
) -> list[DatasetSummary]:
    return service.list_datasets()


@router.post(
    "/upload", response_model=DatasetInfo, status_code=status.HTTP_201_CREATED
)
async def upload_dataset(
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    service: DatasetService = Depends(get_dataset_service),
    session_service: SessionService = Depends(get_session_service),
) -> DatasetInfo:
    if session_id is None or not session_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id is required.",
        )

    dataset = await service.upload(file)
    session_service.attach_dataset(
        session_id.strip(),
        dataset.id,
        title=dataset.filename,
    )
    return dataset


@router.get("/{dataset_id}", response_model=DatasetInfo)
def get_dataset(
    dataset_id: str, service: DatasetService = Depends(get_dataset_service)
) -> DatasetInfo:
    try:
        return service.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' was not found.",
        ) from exc


@router.get("/{dataset_id}/profile", response_model=DatasetProfileResponse)
def get_dataset_profile(
    dataset_id: str,
    service: DatasetService = Depends(get_dataset_service),
) -> DatasetProfileResponse:
    try:
        return service.get_profile(dataset_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' was not found.",
        ) from exc


@router.get("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
def get_dataset_preview(
    dataset_id: str,
    service: DatasetService = Depends(get_dataset_service),
) -> DatasetPreviewResponse:
    try:
        return service.get_preview(dataset_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete("/{dataset_id}", response_model=DatasetDeleteResponse)
def delete_dataset(
    dataset_id: str,
    service: DatasetService = Depends(get_dataset_service),
) -> DatasetDeleteResponse:
    try:
        return service.delete(dataset_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
