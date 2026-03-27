from fastapi import APIRouter, Depends, File, UploadFile, status

from api.deps import get_dataset_service
from domain.datasets.schemas import (
    DatasetDetail,
    DatasetPreviewResponse,
    DatasetProfileResponse,
)
from domain.datasets.service import DatasetService

router = APIRouter()


@router.post(
    "/upload", response_model=DatasetDetail, status_code=status.HTTP_201_CREATED
)
async def upload_dataset(
    file: UploadFile = File(...),
    service: DatasetService = Depends(get_dataset_service),
) -> DatasetDetail:
    return await service.upload(file)


@router.get("/{dataset_id}", response_model=DatasetDetail)
def get_dataset(
    dataset_id: str, service: DatasetService = Depends(get_dataset_service)
) -> DatasetDetail:
    return service.get(dataset_id)


@router.get("/{dataset_id}/profile", response_model=DatasetProfileResponse)
def get_dataset_profile(
    dataset_id: str,
    service: DatasetService = Depends(get_dataset_service),
) -> DatasetProfileResponse:
    return service.get_profile(dataset_id)


@router.get("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
def get_dataset_preview(
    dataset_id: str,
    service: DatasetService = Depends(get_dataset_service),
) -> DatasetPreviewResponse:
    return service.get_preview(dataset_id)
