from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.db.base import Base


def utcnow() -> datetime:
    """DB row 생성 시 사용할 timezone-aware 현재 시각을 반환합니다."""
    return datetime.now(UTC)


class SessionOrm(Base):
    """채팅 세션의 최소 메타데이터를 저장하는 ORM 모델입니다."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    user_messages: Mapped[list["UserMessageOrm"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="UserMessageOrm.created_at",
    )
    agent_runs: Mapped[list["AgentRunOrm"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AgentRunOrm.created_at",
    )
    timeline_items: Mapped[list["AgentTimelineItemOrm"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AgentTimelineItemOrm.sequence",
    )


class DatasetOrm(Base):
    """데이터셋의 논리적 정의와 표시 메타데이터를 저장하는 ORM 모델입니다."""

    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    sources: Mapped[list["DatasetSourceOrm"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="DatasetSourceOrm.created_at",
    )
    workspace_links: Mapped[list["WorkspaceDatasetLinkOrm"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by=lambda: WorkspaceDatasetLinkOrm.linked_at.desc(),
    )


class WorkspaceDatasetLinkOrm(Base):
    """워크스페이스에서 사용자가 명시적으로 연결한 데이터셋입니다."""

    __tablename__ = "workspace_dataset_links"

    workspace_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    dataset_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    dataset: Mapped[DatasetOrm] = relationship(back_populates="workspace_links")


class DatasetSourceOrm(Base):
    """데이터셋이 참조하는 원천 데이터 업로드 row를 저장합니다."""

    __tablename__ = "dataset_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    source_ref_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    dataset: Mapped[DatasetOrm] = relationship(back_populates="sources")
    profile: Mapped["DatasetSourceProfileOrm | None"] = relationship(
        back_populates="dataset_source",
        cascade="all, delete-orphan",
        uselist=False,
    )


class DatasetSourceProfileOrm(Base):
    """데이터셋 등록 시점에 계산한 원천 파일별 preview/profile 스냅샷입니다."""

    __tablename__ = "dataset_source_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_source_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("dataset_sources.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    preview: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    profile: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    dataset_source: Mapped[DatasetSourceOrm] = relationship(back_populates="profile")


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
    agent_runs: Mapped[list["AgentRunOrm"]] = relationship(
        back_populates="user_message",
        cascade="all, delete-orphan",
        order_by="AgentRunOrm.created_at",
    )
    timeline_items: Mapped[list["AgentTimelineItemOrm"]] = relationship(
        back_populates="user_message",
        cascade="all, delete-orphan",
        order_by="AgentTimelineItemOrm.sequence",
    )


class UserMessageDatasetLinkOrm(Base):
    """사용자 메시지와 참조 데이터셋의 연결을 저장합니다."""

    __tablename__ = "user_message_dataset_links"

    user_message_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user_messages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    dataset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user_message: Mapped[UserMessageOrm] = relationship(back_populates="dataset_links")


class AgentRunOrm(Base):
    """사용자 메시지 1개에 대응하는 agent 실행 그룹입니다."""

    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    user_message_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("user_messages.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    session: Mapped[SessionOrm] = relationship(back_populates="agent_runs")
    user_message: Mapped[UserMessageOrm] = relationship(back_populates="agent_runs")
    iterations: Mapped[list["AgentIterationOrm"]] = relationship(
        back_populates="agent_run",
        cascade="all, delete-orphan",
        order_by="AgentIterationOrm.iteration_index",
    )
    timeline_items: Mapped[list["AgentTimelineItemOrm"]] = relationship(
        back_populates="agent_run",
        cascade="all, delete-orphan",
        order_by="AgentTimelineItemOrm.sequence",
    )


class AgentIterationOrm(Base):
    """agent 실행 내부의 LLM API 1회 호출 단위입니다."""

    __tablename__ = "agent_iterations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    iteration_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    agent_run: Mapped[AgentRunOrm] = relationship(back_populates="iterations")
    timeline_items: Mapped[list["AgentTimelineItemOrm"]] = relationship(
        back_populates="agent_iteration",
        cascade="all, delete-orphan",
        order_by="AgentTimelineItemOrm.sequence",
    )


class AgentTimelineItemOrm(Base):
    """프론트 복원과 다음 LLM input 재사용을 위한 agent 타임라인 항목입니다."""

    __tablename__ = "agent_timeline_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    user_message_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("user_messages.id", ondelete="CASCADE"), nullable=True
    )
    agent_run_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=True
    )
    agent_iteration_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("agent_iterations.id", ondelete="CASCADE"), nullable=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    input_item: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    stream_event_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    stream_payload: Mapped[dict[str, object] | None] = mapped_column(
        JSON, nullable=True
    )
    is_frontend_visible: Mapped[bool] = mapped_column(Boolean, default=False)
    is_input_reusable: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    session: Mapped[SessionOrm] = relationship(back_populates="timeline_items")
    user_message: Mapped[UserMessageOrm | None] = relationship(
        back_populates="timeline_items"
    )
    agent_run: Mapped[AgentRunOrm | None] = relationship(
        back_populates="timeline_items"
    )
    agent_iteration: Mapped[AgentIterationOrm | None] = relationship(
        back_populates="timeline_items"
    )
