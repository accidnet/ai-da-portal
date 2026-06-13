from pathlib import Path

import duckdb
import pandas as pd

from core.utils import read_string
from features.data_sources.domain.models import DataSourceItem
from features.data_sources.infrastructure.repositories import DataSourceRepository
from features.tools.workspace_files.context import resolve_workspace_path


def load_source_path(source_id: str) -> Path:
    """source_id로 원천 데이터 파일의 실제 저장 경로를 조회합니다."""
    source_item = get_source_item_or_raise(source_id)
    return resolve_source_file_path(source_item)


def read_datafile_path(arguments: dict[str, object]) -> Path:
    """tool argument의 datafile_path를 workspace 내부 파일 경로로 검증합니다."""
    raw_path = read_required_string(arguments, "datafile_path")
    workspace_path = _resolve_workspace_datafile_path(raw_path)
    if workspace_path is not None:
        return workspace_path

    raise ValueError("datafile_path must point to a readable workspace file.")


def _resolve_workspace_datafile_path(raw_path: str) -> Path | None:
    """chart tool은 CLI와 같은 workspace 상대 dataset 경로만 허용합니다."""
    if Path(raw_path).expanduser().is_absolute():
        return None

    try:
        workspace_path = resolve_workspace_path(raw_path)
    except ValueError:
        return None
    # workspace 내부 hardlink 파일만 DuckDB에 전달해 절대 경로 추측을 피합니다.
    return workspace_path if workspace_path.is_file() else None


def get_source_item_or_raise(source_id: str) -> DataSourceItem:
    """source_id에 해당하는 원천 데이터 노드를 조회하고 없으면 KeyError를 발생시킵니다."""
    items = DataSourceRepository().list_items_by_ids([source_id])
    if not items:
        raise KeyError(source_id)
    return items[0]


def resolve_source_file_path(source_item: DataSourceItem) -> Path:
    """원천 데이터 노드가 실제 파일인지 검증하고 저장 경로를 반환합니다."""
    if source_item.item_type != "file":
        raise ValueError("Source must be a file.")
    if source_item.storage_path is None:
        raise ValueError("Source storage path is missing.")
    return Path(source_item.storage_path)


def read_required_string(arguments: dict[str, object], key: str) -> str:
    """필수 문자열 argument를 읽고 누락 시 오류를 발생시킵니다."""
    value = read_string(arguments.get(key))
    if value is None:
        raise ValueError(f"{key} is required.")
    return value


def read_limit(value: object) -> int:
    """DuckDB SQL 결과 행 제한값을 안전한 범위로 보정합니다."""
    if value is None:
        return 500
    if not isinstance(value, int):
        raise ValueError("limit must be an integer.")
    if value < 1 or value > 5000:
        raise ValueError("limit must be between 1 and 5000.")
    return value


def execute_select_sql(dataset_path: Path, sql: str, limit: int) -> pd.DataFrame:
    """DuckDB가 데이터 파일을 직접 읽는 dataset view를 만들고 SELECT SQL을 실행합니다."""
    normalized_sql = sql.strip().rstrip(";").strip()
    if ";" in normalized_sql:
        raise ValueError("sql must contain a single SELECT statement.")
    if not normalized_sql.lower().startswith(("select ", "with ")):
        raise ValueError("sql must be a read-only SELECT query.")

    connection = duckdb.connect(database=":memory:")
    try:
        create_source_view(connection, dataset_path, "dataset")
        limited_sql = f"SELECT * FROM ({normalized_sql}) AS duckdb_result LIMIT {limit}"
        result = connection.execute(limited_sql).fetchdf()
    except duckdb.Error as exc:
        raise ValueError(f"Failed to execute SQL: {exc}") from exc
    finally:
        connection.close()

    if result.empty:
        raise ValueError("SQL returned no rows.")
    return result


def execute_dataset_sql(dataset_path: Path, sql: str) -> pd.DataFrame:
    """dataset view를 대상으로 한 읽기 SQL을 실행하고 결과 DataFrame만 반환합니다."""
    normalized_sql = _normalize_readonly_sql(sql)
    connection = duckdb.connect(database=":memory:")
    try:
        create_source_view(connection, dataset_path, "dataset")
        return connection.execute(normalized_sql).fetchdf()
    except duckdb.Error as exc:
        raise ValueError(f"Failed to execute SQL: {exc}") from exc
    finally:
        connection.close()


def list_numeric_columns(dataset_path: Path) -> list[str]:
    """DuckDB가 추론한 dataset view schema에서 숫자형 컬럼명을 조회합니다."""
    schema = execute_dataset_sql(dataset_path, "DESCRIBE dataset")
    columns: list[str] = []
    for row in schema.to_dict("records"):
        column_name = row.get("column_name")
        column_type = row.get("column_type")
        if isinstance(column_name, str) and _is_numeric_duckdb_type(column_type):
            columns.append(column_name)
    return columns


def quote_identifier(identifier: str) -> str:
    """DuckDB SQL identifier를 안전하게 quote합니다."""
    if not identifier:
        raise ValueError("Identifier must not be empty.")
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def create_source_view(
    connection: duckdb.DuckDBPyConnection,
    dataset_path: Path,
    view_name: str,
) -> None:
    """저장 파일 확장자에 맞는 DuckDB scan 함수로 source view를 생성합니다."""
    suffix = dataset_path.suffix.lower()
    path_literal = _duckdb_string_literal(str(dataset_path))
    quoted_view_name = quote_identifier(view_name)
    if suffix in {".csv", ".txt"}:
        connection.execute(
            f"CREATE VIEW {quoted_view_name} AS SELECT * FROM read_csv_auto({path_literal})",
        )
        return
    if suffix == ".tsv":
        connection.execute(
            f"CREATE VIEW {quoted_view_name} AS SELECT * FROM read_csv_auto({path_literal}, delim='\t')",
        )
        return
    if suffix == ".json":
        connection.execute(
            f"CREATE VIEW {quoted_view_name} AS SELECT * FROM read_json_auto({path_literal})",
        )
        return
    if suffix == ".parquet":
        connection.execute(
            f"CREATE VIEW {quoted_view_name} AS SELECT * FROM read_parquet({path_literal})",
        )
        return
    raise ValueError(f"Unsupported dataset format for DuckDB SQL: {suffix}")


def _normalize_readonly_sql(sql: str) -> str:
    """단일 SELECT/WITH/DESCRIBE 읽기 SQL만 허용하도록 정규화합니다."""
    normalized_sql = sql.strip().rstrip(";").strip()
    if ";" in normalized_sql:
        raise ValueError("sql must contain a single read-only statement.")
    first_token = normalized_sql.split(maxsplit=1)[0].lower() if normalized_sql else ""
    if first_token not in {"select", "with", "describe"}:
        raise ValueError("sql must be a read-only SELECT/WITH/DESCRIBE query.")
    return normalized_sql


def _is_numeric_duckdb_type(column_type: object) -> bool:
    """DuckDB type 문자열이 분석 가능한 숫자 타입인지 확인합니다."""
    if not isinstance(column_type, str):
        return False
    normalized_type = column_type.upper()
    return any(
        numeric_type in normalized_type
        for numeric_type in (
            "TINYINT",
            "SMALLINT",
            "INTEGER",
            "BIGINT",
            "HUGEINT",
            "UTINYINT",
            "USMALLINT",
            "UINTEGER",
            "UBIGINT",
            "FLOAT",
            "DOUBLE",
            "REAL",
            "DECIMAL",
            "NUMERIC",
        )
    )


def _duckdb_string_literal(value: str) -> str:
    """DuckDB SQL에 삽입할 문자열 literal을 생성합니다."""
    return f"'{value.replace("'", "''")}'"
