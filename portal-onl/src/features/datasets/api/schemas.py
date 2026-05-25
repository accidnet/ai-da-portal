from datetime import datetime

from pydantic import BaseModel, Field

from features.datasets.application.dto import DatasetProfilePayload


class DatasetInfo(BaseModel):
    """데이터셋 기본 정보 응답 모델입니다."""

    # 레거시 업로드 화면 호환을 위해 filename/storage_path 필드를 유지합니다.
    id: str
    filename: str
    name: str | None = None
    description: str | None = None
    storage_path: str | None = None
    created_at: datetime


class DatasetSummary(DatasetInfo):
    """목록 화면에서 사용하는 데이터셋 요약 응답 모델입니다."""

    # 기존 클라이언트 호환 필드와 워크스페이스 연결 정보를 함께 제공합니다.
    row_count: int
    column_count: int
    linked_session_count: int
    linked_session_ids: list[str]
    linked_workspace_count: int
    linked_workspace_ids: list[str]
    latest_used_at: datetime | None = None


class DatasetDeleteResponse(BaseModel):
    """데이터셋 삭제 결과 응답 모델입니다."""

    id: str
    deleted: bool


class DatasetPreviewResponse(BaseModel):
    """데이터셋 미리보기 응답 모델입니다."""

    # 표 미리보기 렌더링에 필요한 컬럼 순서와 행 값을 유지합니다.
    dataset_id: str
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, str | int | float | None]] = Field(default_factory=list)


class DatasetProfileResponse(BaseModel):
    """데이터셋 프로파일 응답 모델입니다."""

    dataset_id: str
    profile: DatasetProfilePayload


class DatasetSourceTreeNode(BaseModel):
    """데이터셋 원천 파일 트리의 단일 노드 응답 모델입니다."""

    # 폴더 노드는 하위 파일의 row/file count를 집계해 반환합니다.
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
    """데이터셋 원천 파일 트리 응답 모델입니다."""

    dataset_id: str
    sources: list[DatasetSourceTreeNode] = Field(default_factory=list)


class CreateDatasetFromSourcesRequest(BaseModel):
    """원천 데이터 선택 기반 데이터셋 생성 요청 모델입니다."""

    # 폴더 ID가 포함되면 application 계층에서 하위 파일로 확장합니다.
    name: str
    description: str | None = None
    data_source_item_ids: list[str] = Field(default_factory=list)
