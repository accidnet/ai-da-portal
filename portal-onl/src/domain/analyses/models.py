from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class AnalysisRun:
    id: str
    session_id: str
    dataset_id: str | None
    analysis_type: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
