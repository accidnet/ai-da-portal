from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class Dataset:
    id: str
    filename: str
    storage_path: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
