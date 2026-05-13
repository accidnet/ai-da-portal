from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from core.config import get_settings
from infrastructure.db.base import Base
from features.data_sources.infrastructure import orm as data_source_db_orm
from features.workspaces.infrastructure import orm as workspace_db_orm
from infrastructure.db import models as db_models

del data_source_db_orm
del workspace_db_orm
del db_models

settings = get_settings()


def _sqlite_connect_args(database_url: str) -> dict[str, bool]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    sqlite_prefix = "sqlite:///"
    if not database_url.startswith(sqlite_prefix):
        return

    database_path = Path(database_url.removeprefix(sqlite_prefix))
    database_path.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_parent_dir(settings.database_url)

engine = create_engine(
    settings.database_url,
    future=True,
    connect_args=_sqlite_connect_args(settings.database_url),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_database() -> None:
    with engine.begin() as connection:
        Base.metadata.create_all(bind=connection)
        inspector = inspect(connection)
        session_columns = {
            column["name"] for column in inspector.get_columns("sessions")
        }
        if "workspace_id" not in session_columns:
            # 기존 SQLite 개발 DB도 새 워크스페이스-세션 관계를 사용할 수 있게 보정합니다.
            connection.execute(text("ALTER TABLE sessions ADD COLUMN workspace_id VARCHAR(64)"))
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_sessions_workspace_id ON sessions (workspace_id)")
            )
