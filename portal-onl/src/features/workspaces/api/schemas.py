from datetime import datetime

from pydantic import BaseModel, Field


class WorkspaceCreateRequest(BaseModel):
    """워크스페이스 생성 요청 payload입니다."""

    name: str = Field(min_length=1, max_length=80)


class WorkspaceUpdateRequest(BaseModel):
    """워크스페이스 수정 요청 payload입니다."""

    name: str = Field(min_length=1, max_length=80)


class WorkspaceResponse(BaseModel):
    """프론트엔드에 반환하는 워크스페이스 응답입니다."""

    id: str
    name: str
    created_at: datetime
    updated_at: datetime


class WorkspaceDeleteResponse(BaseModel):
    """워크스페이스 삭제 응답입니다."""

    id: str
    deleted: bool


class WorkspaceDatasetLinkRequest(BaseModel):
    """워크스페이스 데이터셋 연결 요청 payload입니다."""

    dataset_id: str = Field(min_length=1)


class WorkspaceDatasetLinkResponse(BaseModel):
    """워크스페이스 데이터셋 연결 응답입니다."""

    workspace_id: str
    dataset_ids: list[str]
