from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal


@dataclass(slots=True)
class Message:
    id: str
    session_id: str
    role: Literal["user", "assistant"]
    text: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
