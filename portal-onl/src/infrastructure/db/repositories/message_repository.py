from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from infrastructure.db.models import (
    AgentRunOrm,
    AgentTimelineItemOrm,
    SessionOrm,
    UserMessageDatasetLinkOrm,
    UserMessageOrm,
)
from infrastructure.db.session import SessionLocal
from shared.integrations.ai.contracts import InputItemList, Message, ResponseInputText

SessionTimelineMessageOrm = UserMessageOrm | AgentTimelineItemOrm


class MessageRepository:
    """사용자 메시지와 agent timeline의 ORM 조회 및 영속화를 담당합니다."""

    def record_user_message(
        self,
        *,
        session_id: str,
        user_message: str,
        dataset_ids: list[str],
    ) -> str | None:
        """사용자 메시지와 LLM 재사용 가능한 input item을 함께 저장합니다."""
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
            db.flush()
            self._add_timeline_item(
                db,
                session_id=session_id,
                user_message_id=user_message_row.id,
                input_item=self._build_user_input_item(normalized_message),
                stream_event_type="message.done",
                stream_payload={
                    "role": "user",
                    "text": normalized_message,
                    "dataset_ids": self._dedupe_dataset_ids(dataset_ids),
                },
                is_frontend_visible=True,
                is_input_reusable=True,
                created_at=now,
            )
            self._touch_session(db, session_id, now)
            db.commit()
            return user_message_row.id

    def create_agent_run(self, *, session_id: str, user_message_id: str) -> str:
        """사용자 메시지에 대응하는 agent run을 생성합니다."""
        with SessionLocal() as db:
            self._get_session_or_raise(db, session_id)
            if self._get_user_message(db, session_id, user_message_id) is None:
                raise KeyError(user_message_id)
            agent_run = AgentRunOrm(
                id=str(uuid4()),
                session_id=session_id,
                user_message_id=user_message_id,
                created_at=datetime.now(UTC),
            )
            db.add(agent_run)
            db.commit()
            return agent_run.id

    def record_agent_response(
        self,
        *,
        session_id: str,
        user_message_id: str,
        agent_run_id: str | None,
        assistant_message: str,
        input_item: dict[str, object] | None = None,
        stream_event_type: str = "message.done",
        stream_payload: dict[str, object] | None = None,
        is_frontend_visible: bool = True,
        is_input_reusable: bool | None = None,
    ) -> None:
        """완료된 assistant 응답을 timeline item으로 저장합니다."""
        normalized_message = assistant_message.strip()
        if not normalized_message and stream_payload is None:
            return

        with SessionLocal() as db:
            self._get_session_or_raise(db, session_id)
            if self._get_user_message(db, session_id, user_message_id) is None:
                return

            now = datetime.now(UTC)
            self._add_timeline_item(
                db,
                session_id=session_id,
                user_message_id=user_message_id,
                agent_run_id=agent_run_id,
                input_item=input_item,
                stream_event_type=stream_event_type,
                stream_payload=stream_payload
                or {"role": "assistant", "text": normalized_message},
                is_frontend_visible=is_frontend_visible,
                is_input_reusable=(
                    input_item is not None
                    if is_input_reusable is None
                    else is_input_reusable
                ),
                created_at=now,
            )
            self._touch_session(db, session_id, now)
            db.commit()

    def record_agent_input_items(
        self,
        *,
        session_id: str,
        user_message_id: str,
        agent_run_id: str | None,
        input_items: list[dict[str, object]],
    ) -> None:
        """agent가 생성한 LLM 재사용 input item을 timeline에 저장합니다."""
        reusable_items = [item for item in input_items if isinstance(item, dict)]
        if not reusable_items:
            return

        with SessionLocal() as db:
            self._get_session_or_raise(db, session_id)
            if self._get_user_message(db, session_id, user_message_id) is None:
                return

            now = datetime.now(UTC)
            for input_item in reusable_items:
                self._add_timeline_item(
                    db,
                    session_id=session_id,
                    user_message_id=user_message_id,
                    agent_run_id=agent_run_id,
                    input_item=input_item,
                    stream_event_type=self._read_input_item_type(input_item),
                    stream_payload=None,
                    is_frontend_visible=False,
                    is_input_reusable=True,
                    created_at=now,
                )
            self._touch_session(db, session_id, now)
            db.commit()

    def list_session_timeline(self, session_id: str) -> list[SessionTimelineMessageOrm]:
        """사용자 메시지와 프론트 노출 timeline item을 합쳐 조회합니다."""
        with SessionLocal() as db:
            user_messages = list(
                db.scalars(
                    select(UserMessageOrm)
                    .options(selectinload(UserMessageOrm.dataset_links))
                    .where(UserMessageOrm.session_id == session_id)
                ).all()
            )
            visible_items = list(
                db.scalars(
                    select(AgentTimelineItemOrm).where(
                        AgentTimelineItemOrm.session_id == session_id,
                        AgentTimelineItemOrm.is_frontend_visible.is_(True),
                        AgentTimelineItemOrm.user_message_id.is_not(None),
                    )
                ).all()
            )

        user_item_ids = {
            item.user_message_id
            for item in visible_items
            if item.stream_payload
            and item.stream_payload.get("role") == "user"
        }
        messages: list[SessionTimelineMessageOrm] = [
            *[message for message in user_messages if message.id not in user_item_ids],
            *visible_items,
        ]
        return sorted(messages, key=self._timeline_sort_key)

    def count_session_messages(self, session_id: str) -> int:
        """프론트에 노출되는 세션 메시지 개수를 조회합니다."""
        return len(self.list_session_timeline(session_id))

    def list_session_dataset_ids(self, session_id: str) -> list[str]:
        """사용자 메시지에 연결된 dataset id를 최신 연결 순서로 조회합니다."""
        with SessionLocal() as db:
            rows = db.execute(
                select(UserMessageDatasetLinkOrm.dataset_id)
                .join(
                    UserMessageOrm,
                    UserMessageOrm.id == UserMessageDatasetLinkOrm.user_message_id,
                )
                .where(UserMessageOrm.session_id == session_id)
                .order_by(UserMessageDatasetLinkOrm.linked_at.desc())
            ).all()

        dataset_ids: list[str] = []
        for (dataset_id,) in rows:
            if dataset_id not in dataset_ids:
                dataset_ids.append(dataset_id)
        return dataset_ids

    def _add_timeline_item(
        self,
        db,
        *,
        session_id: str,
        user_message_id: str | None = None,
        agent_run_id: str | None = None,
        agent_iteration_id: str | None = None,
        input_item: dict[str, object] | None,
        stream_event_type: str | None,
        stream_payload: dict[str, object] | None,
        is_frontend_visible: bool,
        is_input_reusable: bool,
        created_at: datetime,
    ) -> AgentTimelineItemOrm:
        """세션 단위 sequence를 부여해 timeline item을 추가합니다."""
        sequence = self._next_sequence(db, session_id)
        item = AgentTimelineItemOrm(
            id=str(uuid4()),
            session_id=session_id,
            user_message_id=user_message_id,
            agent_run_id=agent_run_id,
            agent_iteration_id=agent_iteration_id,
            sequence=sequence,
            input_item=input_item,
            stream_event_type=stream_event_type,
            stream_payload=stream_payload,
            is_frontend_visible=is_frontend_visible,
            is_input_reusable=is_input_reusable,
            created_at=created_at,
        )
        db.add(item)
        return item

    def _next_sequence(self, db, session_id: str) -> int:
        current = db.scalar(
            select(func.max(AgentTimelineItemOrm.sequence)).where(
                AgentTimelineItemOrm.session_id == session_id
            )
        )
        return int(current or 0) + 1

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

    def _build_user_input_item(self, message: str) -> dict[str, object]:
        """사용자 메시지를 Responses API input item payload로 변환합니다."""
        return InputItemList(
            items=(Message(role="user", content=(ResponseInputText(text=message),)),)
        ).to_payload()[0]

    def _read_input_item_type(self, input_item: dict[str, object]) -> str | None:
        """input item payload에서 timeline event type으로 쓸 type 값을 읽습니다."""
        item_type = input_item.get("type")
        return item_type if isinstance(item_type, str) else None

    def _touch_session(self, db, session_id: str, now: datetime) -> None:
        session = db.scalar(select(SessionOrm).where(SessionOrm.id == session_id))
        if session is not None:
            session.updated_at = now

    def _timeline_sort_key(self, item: SessionTimelineMessageOrm) -> tuple[datetime, int]:
        if isinstance(item, AgentTimelineItemOrm):
            return item.created_at, item.sequence
        return item.created_at, 0

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
