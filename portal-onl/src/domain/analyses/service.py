from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from domain.analyses.chart_builders import build_analytics_from_dataframe
from domain.analyses.schemas import (
    AnalysisArtifactsResponse,
    AnalysisDetail,
    AnalysisRequest,
)
from application.datasets.service import DatasetApplicationService
from domain.sessions.service import SessionService
from domain.workspace.service import WorkspacePlanner
from infrastructure.ai.client import AiClient


class AnalysisService:
    def __init__(
        self,
        dataset_service: DatasetApplicationService,
        llm_client: AiClient | None,
        session_service: SessionService,
    ) -> None:
        self._dataset_service = dataset_service
        self._session_service = session_service
        self._analyses: dict[str, _AnalysisRecord] = {}
        self._workspace_planner = WorkspacePlanner(llm_client=llm_client)

    def create(self, payload: AnalysisRequest) -> AnalysisDetail:
        dataset_id = payload.dataset_id or self._dataset_service.get_latest_dataset_id()
        if dataset_id is None:
            raise KeyError("No dataset has been uploaded yet.")

        dataframe = self._dataset_service.get_dataframe(dataset_id)
        analysis_id = str(uuid4())
        analytics = build_analytics_from_dataframe(
            dataframe=dataframe,
            analysis_type=payload.analysis_type,
            prompt=payload.prompt,
        )
        detail = AnalysisDetail(
            id=analysis_id,
            session_id=payload.session_id,
            dataset_id=dataset_id,
            analysis_type=payload.analysis_type,
            status="completed",
            created_at=datetime.now(UTC),
            analytics=analytics,
            workspace=self._workspace_planner.plan(
                prompt=payload.prompt,
                analytics=analytics,
                analysis_type=payload.analysis_type,
                dataset_ids=[dataset_id],
            ),
        )
        self._analyses[analysis_id] = _AnalysisRecord(
            detail=detail,
            notes=[
                f"Built from dataset {dataset_id} with {len(dataframe):,} rows and {len(dataframe.columns)} columns."
            ],
        )
        self._session_service.record_analysis(
            session_id=payload.session_id,
            dataset_id=dataset_id,
            analytics=analytics,
            workspace=detail.workspace,
        )
        return detail

    def get(self, analysis_id: str) -> AnalysisDetail:
        return self._get_record(analysis_id).detail

    def get_artifacts(self, analysis_id: str) -> AnalysisArtifactsResponse:
        record = self._get_record(analysis_id)
        return AnalysisArtifactsResponse(
            analysis_id=analysis_id,
            analytics=record.detail.analytics
            or build_analytics_from_dataframe(
                dataframe=self._dataset_service.get_dataframe(
                    record.detail.dataset_id
                    or self._dataset_service.get_latest_dataset_id()
                    or ""
                ),
                analysis_type=record.detail.analysis_type,
                prompt=None,
            ),
            workspace=record.detail.workspace,
            notes=record.notes,
        )

    def _get_record(self, analysis_id: str) -> "_AnalysisRecord":
        record = self._analyses.get(analysis_id)
        if record is None:
            raise KeyError(analysis_id)
        return record


@dataclass(slots=True)
class _AnalysisRecord:
    detail: AnalysisDetail
    notes: list[str]
