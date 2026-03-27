from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class Dataset:
    id: str
    filename: str
    content_type: str | None
    storage_path: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
