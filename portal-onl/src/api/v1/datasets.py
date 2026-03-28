from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from api.deps import get_dataset_service
from domain.datasets.schemas import (
    DatasetDetail,
    DatasetPreviewResponse,
    DatasetProfileResponse,
)
from domain.datasets.service import DatasetService

router = APIRouter()


@router.get("", response_model=list[DatasetDetail])
def list_datasets(
    service: DatasetService = Depends(get_dataset_service),
) -> list[DatasetDetail]:
    return service.list_datasets()


@router.post(
    "/upload", response_model=DatasetDetail, status_code=status.HTTP_201_CREATED
)
async def upload_dataset(
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    service: DatasetService = Depends(get_dataset_service),
) -> DatasetDetail:
    return await service.upload(file, session_id=session_id)


@router.get("/{dataset_id}", response_model=DatasetDetail)
def get_dataset(
    dataset_id: str, service: DatasetService = Depends(get_dataset_service)
) -> DatasetDetail:
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
