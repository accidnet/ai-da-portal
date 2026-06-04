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


class WorkspaceFileEntryResponse(BaseModel):
    """워크스페이스 로컬 저장소의 파일/폴더 항목 응답입니다."""

    path: str
    name: str
    kind: str
    size_bytes: int | None
    updated_at: datetime


class WorkspaceFileListResponse(BaseModel):
    """워크스페이스 로컬 저장소 목록 조회 응답입니다."""

    workspace_id: str
    path: str
    entries: list[WorkspaceFileEntryResponse]
    has_more: bool


class WorkspaceFileContentResponse(BaseModel):
    """워크스페이스 로컬 텍스트 파일 내용 응답입니다."""

    workspace_id: str
    path: str
    name: str
    size_bytes: int
    content: str | None
    is_binary: bool
    truncated: bool
