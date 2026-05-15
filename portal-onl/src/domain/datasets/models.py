from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class Dataset:
    """데이터셋의 논리적 메타데이터와 최신 분석 artifact 경로입니다."""

    id: str
    filename: str
    name: str | None = None
    description: str | None = None
    storage_path: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
