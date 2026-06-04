from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class WorkspaceCreateCommand:
    """워크스페이스 생성 유스케이스 입력 DTO입니다."""

    name: str


@dataclass(frozen=True, slots=True)
class WorkspaceUpdateCommand:
    """워크스페이스 이름 변경 유스케이스 입력 DTO입니다."""

    name: str


@dataclass(frozen=True, slots=True)
class WorkspaceResult:
    """워크스페이스 조회/변경 유스케이스 출력 DTO입니다."""

    id: str
    name: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class WorkspaceDeleteResult:
    """워크스페이스 삭제 유스케이스 출력 DTO입니다."""

    id: str
    deleted: bool


@dataclass(frozen=True, slots=True)
class WorkspaceDatasetLinkResult:
    """워크스페이스 데이터셋 연결 유스케이스 출력 DTO입니다."""

    workspace_id: str
    dataset_ids: list[str]


@dataclass(frozen=True, slots=True)
class WorkspaceFileEntryResult:
    """워크스페이스 로컬 저장소의 파일/폴더 항목 DTO입니다."""

    path: str
    name: str
    kind: str
    size_bytes: int | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class WorkspaceFileListResult:
    """워크스페이스 로컬 저장소 목록 조회 결과 DTO입니다."""

    workspace_id: str
    path: str
    entries: list[WorkspaceFileEntryResult]
    has_more: bool


@dataclass(frozen=True, slots=True)
class WorkspaceFileContentResult:
    """워크스페이스 로컬 텍스트 파일 읽기 결과 DTO입니다."""

    workspace_id: str
    path: str
    name: str
    size_bytes: int
    content: str | None
    is_binary: bool
    truncated: bool
