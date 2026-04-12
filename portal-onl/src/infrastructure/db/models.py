from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class SessionOrm(Base):
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
    dataset_links: Mapped[list["SessionDatasetLinkOrm"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SessionDatasetLinkOrm.linked_at.desc()",
    )


class SessionMessageOrm(Base):
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


class SessionDatasetLinkOrm(Base):
    __tablename__ = "session_dataset_links"

    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    dataset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[SessionOrm] = relationship(back_populates="dataset_links")
