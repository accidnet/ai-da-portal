from fastapi import APIRouter, Depends, status

from portal_onl.api.deps import get_analysis_service
from portal_onl.domain.analyses.schemas import (
    AnalysisArtifactsResponse,
    AnalysisDetail,
    AnalysisRequest,
)
from portal_onl.domain.analyses.service import AnalysisService

router = APIRouter()


@router.post("", response_model=AnalysisDetail, status_code=status.HTTP_202_ACCEPTED)
def create_analysis(
    payload: AnalysisRequest,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisDetail:
    return service.create(payload)


@router.get("/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(
    analysis_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisDetail:
    return service.get(analysis_id)


@router.get("/{analysis_id}/artifacts", response_model=AnalysisArtifactsResponse)
def get_analysis_artifacts(
    analysis_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisArtifactsResponse:
    return service.get_artifacts(analysis_id)
