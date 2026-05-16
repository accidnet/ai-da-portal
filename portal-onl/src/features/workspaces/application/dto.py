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
