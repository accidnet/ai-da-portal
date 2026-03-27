from datetime import UTC, datetime
from uuid import uuid4

from portal_onl.domain.analyses.chart_builders import (
    build_demo_cards,
    build_demo_chart,
    build_demo_table,
)
from portal_onl.domain.analyses.schemas import (
    AnalysisArtifactsResponse,
    AnalysisDetail,
    AnalysisRequest,
)
from portal_onl.domain.shared import AnalyticsPayload, InsightPayload


class AnalysisService:
    def create(self, payload: AnalysisRequest) -> AnalysisDetail:
        analysis_id = str(uuid4())
        analytics = self._build_placeholder_analytics(payload.analysis_type)
        return AnalysisDetail(
            id=analysis_id,
            session_id=payload.session_id,
            dataset_id=payload.dataset_id,
            analysis_type=payload.analysis_type,
            status="completed",
            created_at=datetime.now(UTC),
            analytics=analytics,
        )

    def get(self, analysis_id: str) -> AnalysisDetail:
        return AnalysisDetail(
            id=analysis_id,
            session_id="demo-session",
            dataset_id="demo-dataset",
            analysis_type="dataset_profile",
            status="completed",
            created_at=datetime.now(UTC),
            analytics=self._build_placeholder_analytics("dataset_profile"),
        )

    def get_artifacts(self, analysis_id: str) -> AnalysisArtifactsResponse:
        return AnalysisArtifactsResponse(
            analysis_id=analysis_id,
            analytics=self._build_placeholder_analytics("dataset_profile"),
            notes=[
                "Placeholder artifact payload until analysis tools are wired to real datasets."
            ],
        )

    def _build_placeholder_analytics(self, analysis_type: str) -> AnalyticsPayload:
        return AnalyticsPayload(
            summary_cards=build_demo_cards(),
            charts=[
                build_demo_chart(f"{analysis_type.replace('_', ' ').title()} Output")
            ],
            tables=[build_demo_table()],
            insights=[
                InsightPayload(
                    title="Scaffold Ready",
                    body="The API can now return chart, metric, and table contracts that match the dashboard-oriented frontend.",
                    action_label="Connect Real Tools",
                )
            ],
        )
