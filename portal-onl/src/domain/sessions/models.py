from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class Session:
    id: str
    title: str
    preferred_dataset_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
