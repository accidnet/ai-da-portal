from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class Workspace:
    """사용자가 생성한 포털 워크스페이스입니다."""

    id: str
    name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
