from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import sessionmaker

from core.config import get_settings
from infrastructure.db.base import Base
from infrastructure.db import models as db_models

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
        _ensure_dataset_json_columns(connection)
        _ensure_bot_response_json_columns(connection)


def _ensure_dataset_json_columns(connection: Connection) -> None:
    """기존 SQLite datasets 테이블에 신규 JSON 컬럼을 보정합니다."""
    if connection.dialect.name != "sqlite":
        return

    inspector = inspect(connection)
    if "datasets" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("datasets")}
    for column_name in ("preview", "profile"):
        if column_name in columns:
            continue
        connection.execute(
            text(f"ALTER TABLE datasets ADD COLUMN {column_name} JSON")
        )


def _ensure_bot_response_json_columns(connection: Connection) -> None:
    """기존 SQLite bot_responses 테이블에 신규 JSON 컬럼을 보정합니다."""
    if connection.dialect.name != "sqlite":
        return

    inspector = inspect(connection)
    if "bot_responses" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("bot_responses")}
    if "sub_messages" not in columns:
        connection.execute(text("ALTER TABLE bot_responses ADD COLUMN sub_messages JSON"))
