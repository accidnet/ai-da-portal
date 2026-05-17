from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from api.deps import get_dataset_service, get_session_service
from domain.sessions.service import SessionService
from features.datasets.api.schemas import (
    CreateDatasetFromSourcesRequest,
    DatasetDeleteResponse,
    DatasetInfo,
    DatasetPreviewResponse,
    DatasetProfileResponse,
    DatasetSourcesResponse,
    DatasetSummary,
)
from features.datasets.application.service import DatasetApplicationService

router = APIRouter()


@router.get("", response_model=list[DatasetSummary])
def list_datasets(
    service: DatasetApplicationService = Depends(get_dataset_service),
) -> list[DatasetSummary]:
    """등록된 데이터셋 목록을 최신순으로 반환합니다."""
    return service.list_datasets()


@router.post(
    "/upload", response_model=DatasetInfo, status_code=status.HTTP_201_CREATED
)
async def upload_dataset(
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    service: DatasetApplicationService = Depends(get_dataset_service),
    session_service: SessionService = Depends(get_session_service),
) -> DatasetInfo:
    """파일 업로드로 데이터셋을 생성하고 세션에 연결합니다."""
    if session_id is None or not session_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id is required.",
        )

    dataset = await service.upload(file)
    try:
        session_service.attach_dataset(
            session_id.strip(),
            dataset.id,
            title=dataset.filename,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return dataset


@router.post("", response_model=DatasetInfo, status_code=status.HTTP_201_CREATED)
def create_dataset_from_sources(
    request: CreateDatasetFromSourcesRequest,
    service: DatasetApplicationService = Depends(get_dataset_service),
) -> DatasetInfo:
    """원천 데이터 선택 정보로 데이터셋을 생성합니다."""
    try:
        return service.create_from_sources(request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/{dataset_id}", response_model=DatasetInfo)
def get_dataset(
    dataset_id: str, service: DatasetApplicationService = Depends(get_dataset_service)
) -> DatasetInfo:
    """데이터셋 ID로 기본 정보를 조회합니다."""
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
    service: DatasetApplicationService = Depends(get_dataset_service),
) -> DatasetProfileResponse:
    """데이터셋 ID로 프로파일 정보를 조회합니다."""
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
    service: DatasetApplicationService = Depends(get_dataset_service),
) -> DatasetPreviewResponse:
    """데이터셋 ID로 미리보기 정보를 조회합니다."""
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


@router.get("/{dataset_id}/sources", response_model=DatasetSourcesResponse)
def get_dataset_sources(
    dataset_id: str,
    service: DatasetApplicationService = Depends(get_dataset_service),
) -> DatasetSourcesResponse:
    """데이터셋 ID로 연결된 원천 파일 트리를 조회합니다."""
    try:
        return service.get_sources(dataset_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' was not found.",
        ) from exc


@router.delete("/{dataset_id}", response_model=DatasetDeleteResponse)
def delete_dataset(
    dataset_id: str,
    service: DatasetApplicationService = Depends(get_dataset_service),
) -> DatasetDeleteResponse:
    """데이터셋을 삭제합니다."""
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
