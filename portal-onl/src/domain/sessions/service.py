from datetime import UTC, datetime
from uuid import uuid4

from domain.sessions.schemas import (
    SessionCreateRequest,
    SessionDetail,
    SessionSummary,
)


class SessionService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self._sessions: dict[str, SessionDetail] = {
            "demo-session": SessionDetail(
                id="demo-session",
                title="Marketing performance review",
                created_at=now,
                updated_at=now,
            )
        }

    def create(self, payload: SessionCreateRequest) -> SessionDetail:
        now = datetime.now(UTC)
        session_id = str(uuid4())
        session = SessionDetail(
            id=session_id, title=payload.title, created_at=now, updated_at=now
        )
        self._sessions[session_id] = session
        return session

    def list_sessions(self) -> list[SessionSummary]:
        return sorted(
            [
                SessionSummary(
                    id=session.id,
                    title=session.title,
                    updated_at=session.updated_at,
                )
                for session in self._sessions.values()
            ],
            key=lambda session: session.updated_at,
            reverse=True,
        )

    def get(self, session_id: str) -> SessionDetail:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session
