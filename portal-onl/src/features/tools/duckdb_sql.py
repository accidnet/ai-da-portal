from pathlib import Path

import duckdb
import pandas as pd

from core.utils import read_string
from features.data_sources.domain.models import DataSourceItem
from features.data_sources.infrastructure.repositories import DataSourceRepository


def load_source_path(source_id: str) -> Path:
    """source_id로 원천 데이터 파일의 실제 저장 경로를 조회합니다."""
    source_item = get_source_item_or_raise(source_id)
    return resolve_source_file_path(source_item)


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
        _create_dataset_view(connection, dataset_path)
        limited_sql = f"SELECT * FROM ({normalized_sql}) AS duckdb_result LIMIT {limit}"
        result = connection.execute(limited_sql).fetchdf()
    except duckdb.Error as exc:
        raise ValueError(f"Failed to execute SQL: {exc}") from exc
    finally:
        connection.close()

    if result.empty:
        raise ValueError("SQL returned no rows.")
    return result


def _create_dataset_view(connection: duckdb.DuckDBPyConnection, dataset_path: Path) -> None:
    """저장 파일 확장자에 맞는 DuckDB scan 함수로 dataset view를 생성합니다."""
    suffix = dataset_path.suffix.lower()
    path_literal = _duckdb_string_literal(str(dataset_path))
    if suffix in {".csv", ".txt"}:
        connection.execute(
            f"CREATE VIEW dataset AS SELECT * FROM read_csv_auto({path_literal})",
        )
        return
    if suffix == ".tsv":
        connection.execute(
            f"CREATE VIEW dataset AS SELECT * FROM read_csv_auto({path_literal}, delim='\t')",
        )
        return
    if suffix == ".json":
        connection.execute(
            f"CREATE VIEW dataset AS SELECT * FROM read_json_auto({path_literal})",
        )
        return
    if suffix == ".parquet":
        connection.execute(
            f"CREATE VIEW dataset AS SELECT * FROM read_parquet({path_literal})",
        )
        return
    raise ValueError(f"Unsupported dataset format for DuckDB SQL: {suffix}")


def _duckdb_string_literal(value: str) -> str:
    """DuckDB SQL에 삽입할 문자열 literal을 생성합니다."""
    return f"'{value.replace("'", "''")}'"
