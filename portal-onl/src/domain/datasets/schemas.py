from datetime import datetime

from pydantic import BaseModel, Field

from domain.shared import DatasetProfilePayload


class DatasetInfo(BaseModel):
    id: str
    filename: str
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
