from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DataSourceUploadFile:
    """원천 데이터 직접 업로드 대상 파일입니다."""

    filename: str
    content: bytes
    content_type: str | None = None


@dataclass(frozen=True, slots=True)
class DataSourceUploadCommand:
    """원천 데이터 직접 업로드 유스케이스 입력 DTO입니다."""

    files: list[DataSourceUploadFile]
    relative_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DataSourceItemResult:
    """원천 데이터 파일/폴더 노드 응답 DTO입니다."""

    id: str
    parent_id: str | None
    item_type: str
    name: str
    relative_path: str
    depth: int
    sort_order: int
    content_type: str | None
    size_bytes: int | None
    storage_path: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class DataSourceUploadResult:
    """원천 데이터 직접 업로드 결과 DTO입니다."""

    items: list[DataSourceItemResult]


@dataclass(frozen=True, slots=True)
class DataSourceDeleteResult:
    """원천 데이터 파일/폴더 삭제 결과 DTO입니다."""

    id: str
    deleted: bool
    deleted_count: int
