from datetime import datetime

from pydantic import BaseModel, Field


class DataSourceItemResponse(BaseModel):
    """원천 데이터 파일/폴더 노드 응답입니다."""

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
    children: list["DataSourceItemResponse"] = Field(default_factory=list)


class DataSourceUploadResponse(BaseModel):
    """원천 데이터 직접 업로드 결과 응답입니다."""

    items: list[DataSourceItemResponse]


class DataSourceTreeResponse(BaseModel):
    """원천 데이터 트리 조회 응답입니다."""

    items: list[DataSourceItemResponse]


class DataSourceDeleteResponse(BaseModel):
    """원천 데이터 삭제 응답입니다."""

    id: str
    deleted: bool
    deleted_count: int
