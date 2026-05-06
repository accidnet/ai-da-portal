from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class SessionOrm(Base):
    """채팅 세션의 기본 상태와 연결 데이터를 저장하는 ORM 모델입니다."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(60), nullable=False)
    preferred_dataset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analytics: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    workspace: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    messages: Mapped[list["SessionMessageOrm"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SessionMessageOrm.created_at",
    )
    user_messages: Mapped[list["UserMessageOrm"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="UserMessageOrm.created_at",
    )
    bot_responses: Mapped[list["BotResponseOrm"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="BotResponseOrm.created_at",
    )
    dataset_links: Mapped[list["SessionDatasetLinkOrm"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SessionDatasetLinkOrm.linked_at.desc()",
    )


class SessionMessageOrm(Base):
    """이전 단일 메시지 테이블과의 호환을 유지하는 ORM 모델입니다."""

    __tablename__ = "session_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    route: Mapped[str | None] = mapped_column(String(32), nullable=True)
    used_tools: Mapped[list[str]] = mapped_column(JSON, default=list)
    plan: Mapped[list[dict[str, str]] | None] = mapped_column(JSON, nullable=True)
    plan_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    session: Mapped[SessionOrm] = relationship(back_populates="messages")


class UserMessageOrm(Base):
    """사용자가 입력한 원문 메시지를 세션 단위로 저장하는 ORM 모델입니다."""

    __tablename__ = "user_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    session: Mapped[SessionOrm] = relationship(back_populates="user_messages")
    dataset_links: Mapped[list["UserMessageDatasetLinkOrm"]] = relationship(
        back_populates="user_message",
        cascade="all, delete-orphan",
        order_by="UserMessageDatasetLinkOrm.linked_at",
    )
    bot_responses: Mapped[list["BotResponseOrm"]] = relationship(
        back_populates="user_message",
        cascade="all, delete-orphan",
        order_by="BotResponseOrm.created_at",
    )


class UserMessageDatasetLinkOrm(Base):
    """사용자 메시지와 참조 데이터셋의 선택적 연결을 저장합니다."""

    __tablename__ = "user_message_dataset_links"

    user_message_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user_messages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    dataset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user_message: Mapped[UserMessageOrm] = relationship(back_populates="dataset_links")


class DatasetOrm(Base):
    """업로드 데이터셋의 파일 메타데이터를 저장하는 ORM 모델입니다."""

    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    preview: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    profile: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class BotResponseOrm(Base):
    """사용자 메시지에 대응하는 봇 응답과 응답 메타데이터를 저장합니다."""

    __tablename__ = "bot_responses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    user_message_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("user_messages.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    route: Mapped[str | None] = mapped_column(String(32), nullable=True)
    used_tools: Mapped[list[str]] = mapped_column(JSON, default=list)
    plan: Mapped[list[dict[str, str]] | None] = mapped_column(JSON, nullable=True)
    plan_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    sub_messages: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    session: Mapped[SessionOrm] = relationship(back_populates="bot_responses")
    user_message: Mapped[UserMessageOrm] = relationship(back_populates="bot_responses")


class SessionDatasetLinkOrm(Base):
    """세션과 데이터셋의 연결 이력을 저장하는 ORM 모델입니다."""

    __tablename__ = "session_dataset_links"

    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    dataset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[SessionOrm] = relationship(back_populates="dataset_links")
