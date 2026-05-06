from datetime import UTC, datetime
from uuid import uuid4

from infrastructure.db.models import (
    BotResponseOrm,
    SessionMessageOrm,
    SessionOrm,
    UserMessageDatasetLinkOrm,
    UserMessageOrm,
)
from infrastructure.db.session import SessionLocal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

SessionTimelineMessageOrm = SessionMessageOrm | UserMessageOrm | BotResponseOrm


class MessageRepository:
    """채팅 메시지와 봇 응답의 ORM 조회 및 영속화를 담당합니다."""

    def record_user_message(
        self,
        *,
        session_id: str,
        user_message: str,
        dataset_ids: list[str],
    ) -> str | None:
        """이미 존재하는 세션에 내용이 있는 사용자 메시지를 저장합니다."""
        normalized_message = user_message.strip()
        if not normalized_message:
            return None

        with SessionLocal() as db:
            now = datetime.now(UTC)
            user_message_row = UserMessageOrm(
                id=str(uuid4()),
                session_id=session_id,
                text=normalized_message,
                created_at=now,
            )
            db.add(user_message_row)
            for dataset_id in self._dedupe_dataset_ids(dataset_ids):
                db.add(
                    UserMessageDatasetLinkOrm(
                        user_message_id=user_message_row.id,
                        dataset_id=dataset_id,
                        linked_at=now,
                    )
                )
            db.commit()
            return user_message_row.id

    def record_bot_response(
        self,
        *,
        session_id: str,
        user_message_id: str,
        assistant_message: str,
        route: str,
        used_tools: list[str],
        plan: list[dict[str, str]],
        plan_explanation: str | None,
        sub_messages: list[dict[str, object]],
        status: str,
    ) -> None:
        """저장된 사용자 메시지에 봇 응답을 연결합니다."""
        with SessionLocal() as db:
            self._get_session_or_raise(db, session_id)
            if self._get_user_message(db, session_id, user_message_id) is None:
                return

            db.add(
                BotResponseOrm(
                    id=str(uuid4()),
                    session_id=session_id,
                    user_message_id=user_message_id,
                    text=assistant_message,
                    route=route,
                    used_tools=used_tools,
                    plan=plan,
                    plan_explanation=plan_explanation,
                    sub_messages=sub_messages,
                    status=status,
                    created_at=datetime.now(UTC),
                )
            )
            db.commit()

    def list_session_timeline(self, session_id: str) -> list[SessionTimelineMessageOrm]:
        """기존/신규 메시지 테이블을 합쳐 세션 타임라인으로 조회합니다."""
        with SessionLocal() as db:
            legacy_messages = list(
                db.scalars(
                    select(SessionMessageOrm).where(
                        SessionMessageOrm.session_id == session_id
                    )
                ).all()
            )
            user_messages = list(
                db.scalars(
                    select(UserMessageOrm)
                    .options(selectinload(UserMessageOrm.dataset_links))
                    .where(UserMessageOrm.session_id == session_id)
                ).all()
            )
            bot_responses = list(
                db.scalars(
                    select(BotResponseOrm).where(BotResponseOrm.session_id == session_id)
                ).all()
            )
            messages: list[SessionTimelineMessageOrm] = [
                *legacy_messages,
                *user_messages,
                *bot_responses,
            ]
            return sorted(messages, key=lambda message: message.created_at)

    def count_session_messages(self, session_id: str) -> int:
        """기존/신규 메시지 테이블의 메시지 수를 합산합니다."""
        with SessionLocal() as db:
            legacy_count = len(
                db.scalars(
                    select(SessionMessageOrm.id).where(
                        SessionMessageOrm.session_id == session_id
                    )
                ).all()
            )
            user_count = len(
                db.scalars(
                    select(UserMessageOrm.id).where(
                        UserMessageOrm.session_id == session_id
                    )
                ).all()
            )
            response_count = len(
                db.scalars(
                    select(BotResponseOrm.id).where(
                        BotResponseOrm.session_id == session_id
                    )
                ).all()
            )
            return legacy_count + user_count + response_count

    def _get_session_or_raise(self, db, session_id: str) -> SessionOrm:
        session = db.scalar(select(SessionOrm).where(SessionOrm.id == session_id))
        if session is None:
            raise KeyError(session_id)
        return session

    def _get_user_message(
        self, db, session_id: str, user_message_id: str
    ) -> UserMessageOrm | None:
        return db.scalar(
            select(UserMessageOrm).where(
                UserMessageOrm.id == user_message_id,
                UserMessageOrm.session_id == session_id,
            )
        )

    def _dedupe_dataset_ids(self, dataset_ids: list[str]) -> list[str]:
        resolved_dataset_ids: list[str] = []
        for dataset_id in dataset_ids:
            normalized_dataset_id = dataset_id.strip()
            if (
                normalized_dataset_id
                and normalized_dataset_id not in resolved_dataset_ids
            ):
                resolved_dataset_ids.append(normalized_dataset_id)
        return resolved_dataset_ids
