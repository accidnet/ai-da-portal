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

        dataset_columns = {column["name"] for column in inspector.get_columns("datasets")}
        dataset_column_patches = {
            "name": "ALTER TABLE datasets ADD COLUMN name VARCHAR(255)",
            "description": "ALTER TABLE datasets ADD COLUMN description TEXT",
            "updated_at": "ALTER TABLE datasets ADD COLUMN updated_at DATETIME",
        }
        for column_name, statement in dataset_column_patches.items():
            if column_name not in dataset_columns:
                # 개발 DB가 이미 있어도 신규 데이터셋 aggregate 메타데이터를 저장합니다.
                connection.execute(text(statement))

        refreshed_dataset_columns = {
            column["name"] for column in inspect(connection).get_columns("datasets")
        }
        if "filename" in refreshed_dataset_columns and "name" in refreshed_dataset_columns:
            connection.execute(
                text("UPDATE datasets SET name = COALESCE(name, filename) WHERE name IS NULL")
            )
        if "updated_at" in refreshed_dataset_columns:
            connection.execute(
                text("UPDATE datasets SET updated_at = COALESCE(updated_at, created_at)")
            )

        legacy_dataset_columns = {"filename", "storage_path", "preview", "profile"}
        if legacy_dataset_columns.issubset(refreshed_dataset_columns):
            # 기존 단일 datasets 테이블 row를 source 연결 구조로 1회 이관합니다.
            connection.execute(
                text(
                    """
                    INSERT INTO dataset_sources (
                        id,
                        dataset_id,
                        source_ref_id,
                        created_at
                    )
                    SELECT
                        lower(hex(randomblob(16))),
                        datasets.id,
                        NULL,
                        datasets.created_at
                    FROM datasets
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM dataset_sources
                        WHERE dataset_sources.dataset_id = datasets.id
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO dataset_source_profiles (
                        id,
                        dataset_source_id,
                        row_count,
                        column_count,
                        preview,
                        profile,
                        created_at
                    )
                    SELECT
                        lower(hex(randomblob(16))),
                        dataset_sources.id,
                        0,
                        0,
                        datasets.preview,
                        datasets.profile,
                        datasets.created_at
                    FROM datasets
                    JOIN dataset_sources
                        ON dataset_sources.dataset_id = datasets.id
                    WHERE (datasets.preview IS NOT NULL OR datasets.profile IS NOT NULL)
                        AND NOT EXISTS (
                            SELECT 1
                            FROM dataset_source_profiles
                            WHERE dataset_source_profiles.dataset_source_id = dataset_sources.id
                        )
                    """
                )
            )

            # legacy NOT NULL 컬럼(filename/storage_path 등)을 제거해 datasets를 정의 테이블로 재작성합니다.
            connection.execute(text("PRAGMA foreign_keys=OFF"))
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS datasets_rebuilt (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        name VARCHAR(255),
                        description TEXT,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT OR IGNORE INTO datasets_rebuilt (
                        id,
                        name,
                        description,
                        created_at,
                        updated_at
                    )
                    SELECT
                        id,
                        name,
                        description,
                        created_at,
                        COALESCE(updated_at, created_at)
                    FROM datasets
                    """
                )
            )
            connection.execute(text("DROP TABLE datasets"))
            connection.execute(text("ALTER TABLE datasets_rebuilt RENAME TO datasets"))
            connection.execute(text("PRAGMA foreign_keys=ON"))

        table_names = set(inspect(connection).get_table_names())
        if "dataset_sources" in table_names:
            source_columns = {
                column["name"] for column in inspect(connection).get_columns("dataset_sources")
            }
            if {"source_type", "source_path", "config"}.intersection(source_columns):
                # source_ref_id만 기준으로 쓰도록 dataset_sources 테이블을 단순화합니다.
                connection.execute(text("PRAGMA foreign_keys=OFF"))
                connection.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS dataset_sources_rebuilt (
                            id VARCHAR(64) NOT NULL PRIMARY KEY,
                            dataset_id VARCHAR(64) NOT NULL,
                            source_ref_id VARCHAR(64),
                            created_at DATETIME,
                            FOREIGN KEY(dataset_id) REFERENCES datasets (id) ON DELETE CASCADE
                        )
                        """
                    )
                )
                where_expression = (
                    "WHERE COALESCE(source_type, '') != 'materialized_file'"
                    if "source_type" in source_columns
                    else ""
                )
                connection.execute(
                    text(
                        f"""
                        INSERT OR IGNORE INTO dataset_sources_rebuilt (
                            id,
                            dataset_id,
                            source_ref_id,
                            created_at
                        )
                        SELECT
                            id,
                            dataset_id,
                            source_ref_id,
                            created_at
                        FROM dataset_sources
                        {where_expression}
                        """
                    )
                )
                connection.execute(text("DROP TABLE dataset_sources"))
                connection.execute(
                    text("ALTER TABLE dataset_sources_rebuilt RENAME TO dataset_sources")
                )
                connection.execute(
                    text("CREATE INDEX IF NOT EXISTS ix_dataset_sources_dataset_id ON dataset_sources (dataset_id)")
                )
                connection.execute(text("PRAGMA foreign_keys=ON"))

        # 산출물 테이블은 원천 데이터 업로드 DB를 직접 참조하는 구조로 제거합니다.
        if "dataset_artifacts" in set(inspect(connection).get_table_names()):
            connection.execute(text("DROP TABLE dataset_artifacts"))
        if "dataset_source_artifacts" in set(inspect(connection).get_table_names()):
            connection.execute(text("DROP TABLE dataset_source_artifacts"))
