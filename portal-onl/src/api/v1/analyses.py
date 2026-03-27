from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_analysis_service
from domain.analyses.schemas import (
    AnalysisArtifactsResponse,
    AnalysisDetail,
    AnalysisRequest,
)
from domain.analyses.service import AnalysisService

router = APIRouter()


@router.post("", response_model=AnalysisDetail, status_code=status.HTTP_202_ACCEPTED)
def create_analysis(
    payload: AnalysisRequest,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisDetail:
    try:
        return service.create(payload)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(
    analysis_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisDetail:
    try:
        return service.get(analysis_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis '{analysis_id}' was not found.",
        ) from exc


@router.get("/{analysis_id}/artifacts", response_model=AnalysisArtifactsResponse)
def get_analysis_artifacts(
    analysis_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisArtifactsResponse:
    try:
        return service.get_artifacts(analysis_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis '{analysis_id}' was not found.",
        ) from exc
