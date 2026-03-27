from datetime import datetime

from pydantic import BaseModel, Field

from portal_onl.domain.shared import DatasetProfilePayload


class DatasetDetail(BaseModel):
    id: str
    filename: str
    content_type: str | None = None
    storage_path: str
    created_at: datetime


class DatasetPreviewResponse(BaseModel):
    dataset_id: str
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, str | int | float | None]] = Field(default_factory=list)


class DatasetProfileResponse(BaseModel):
    dataset_id: str
    profile: DatasetProfilePayload
