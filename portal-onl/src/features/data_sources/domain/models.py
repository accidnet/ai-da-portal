from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class DataSourceItem:
    """원천 데이터 트리를 재현하기 위한 파일 또는 폴더 노드입니다."""

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
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
