from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from application.datasets.dto import DatasetProfilePayload

ToolData = TypeVar("ToolData")


class ToolExecutionError(BaseModel):
    """tool 실행 중 발생한 실패 항목을 표현하는 전역 DTO입니다."""

    # target_id는 dataset_id처럼 실패 대상 식별자가 있을 때 사용합니다.
    message: str
    target_id: str | None = None


class ToolExecutionResult(BaseModel, Generic[ToolData]):
    """모든 tool execute 함수에서 사용할 공통 반환 DTO입니다."""

    # 각 tool의 구체적인 결과는 data에 담고, 공통 성공/실패 상태는 최상위에 둡니다.
    ok: bool
    data: ToolData | None = None
    errors: list[ToolExecutionError] = Field(default_factory=list)
    error: str | None = None


class DatasetToolProfilePayload(BaseModel):
    """tool 응답에서 사용하는 데이터셋 프로파일 DTO입니다."""

    # LLM이 여러 데이터셋 결과를 비교할 수 있도록 각 payload에 dataset_id를 포함합니다.
    dataset_id: str
    profile: DatasetProfilePayload


class DatasetToolPreviewPayload(BaseModel):
    """tool 응답에서 사용하는 데이터셋 미리보기 DTO입니다."""

    # 미리보기는 컬럼 목록과 행 샘플을 dataset_id와 함께 전달합니다.
    dataset_id: str
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, str | int | float | None]] = Field(default_factory=list)


class DatasetInspectionPayload(BaseModel):
    """단일 데이터셋 inspect 결과 DTO입니다."""

    # 단일/복수 조회 모두 같은 항목 구조를 사용합니다.
    dataset_id: str
    profile: DatasetToolProfilePayload
    preview: DatasetToolPreviewPayload


class DatasetInspectionData(BaseModel):
    """데이터셋 inspect tool의 data payload DTO입니다."""

    # 단일 조회 호환을 위해 dataset_id/profile/preview 최상위 필드를 선택적으로 유지합니다.
    dataset_ids: list[str] = Field(default_factory=list)
    datasets: list[DatasetInspectionPayload] = Field(default_factory=list)
    dataset_id: str | None = None
    profile: DatasetToolProfilePayload | None = None
    preview: DatasetToolPreviewPayload | None = None
