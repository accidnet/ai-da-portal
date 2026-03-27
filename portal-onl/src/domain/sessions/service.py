from datetime import UTC, datetime
from uuid import uuid4

from domain.sessions.schemas import (
    SessionCreateRequest,
    SessionDetail,
    SessionSummary,
)


class SessionService:
    def create(self, payload: SessionCreateRequest) -> SessionDetail:
        now = datetime.now(UTC)
        session_id = str(uuid4())
        return SessionDetail(
            id=session_id, title=payload.title, created_at=now, updated_at=now
        )

    def list_sessions(self) -> list[SessionSummary]:
        now = datetime.now(UTC)
        return [
            SessionSummary(
                id="demo-session", title="Marketing performance review", updated_at=now
            )
        ]

    def get(self, session_id: str) -> SessionDetail:
        now = datetime.now(UTC)
        return SessionDetail(
            id=session_id,
            title="Marketing performance review",
            created_at=now,
            updated_at=now,
        )
