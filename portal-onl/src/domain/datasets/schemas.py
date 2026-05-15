from datetime import datetime

from pydantic import BaseModel, Field

from application.datasets.dto import DatasetProfilePayload


class DatasetInfo(BaseModel):
    id: str
    filename: str
    name: str | None = None
    description: str | None = None
    storage_path: str | None = None
    created_at: datetime


class DatasetSummary(DatasetInfo):
    row_count: int
    column_count: int
    linked_session_count: int
    linked_session_ids: list[str]
    latest_used_at: datetime | None = None


class DatasetDeleteResponse(BaseModel):
    id: str
    deleted: bool


class DatasetPreviewResponse(BaseModel):
    dataset_id: str
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, str | int | float | None]] = Field(default_factory=list)


class DatasetProfileResponse(BaseModel):
    dataset_id: str
    profile: DatasetProfilePayload


class DatasetSourceTreeNode(BaseModel):
    id: str
    source_ref_id: str | None = None
    item_type: str
    name: str
    relative_path: str
    depth: int
    content_type: str | None = None
    size_bytes: int | None = None
    row_count: int = 0
    column_count: int = 0
    file_count: int = 0
    children: list["DatasetSourceTreeNode"] = Field(default_factory=list)


class DatasetSourcesResponse(BaseModel):
    dataset_id: str
    sources: list[DatasetSourceTreeNode] = Field(default_factory=list)


class CreateDatasetFromSourcesRequest(BaseModel):
    name: str
    description: str | None = None
    data_source_item_ids: list[str] = Field(default_factory=list)
