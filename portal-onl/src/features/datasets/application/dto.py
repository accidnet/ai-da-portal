from pydantic import BaseModel, Field

type DatasetProfileValue = str | int | float | None


class DatasetPreviewPayload(BaseModel):
    """DataFrame에서 생성한 데이터셋 미리보기 payload입니다."""

    # 화면 미리보기에 필요한 컬럼명과 행 데이터만 전달합니다.
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, str | int | float | None]] = Field(default_factory=list)


class DatasetColumnProfile(BaseModel):
    """DataFrame 컬럼별 프로파일 정보를 담는 DTO입니다."""

    # 데이터셋 프로파일 화면과 분석 컨텍스트에서 공통으로 사용합니다.
    name: str
    dtype: str
    null_ratio: float = 0.0
    min_value: DatasetProfileValue = None
    max_value: DatasetProfileValue = None
    sample_values: list[str] = Field(default_factory=list)


class DatasetProfilePayload(BaseModel):
    """DataFrame 전체 프로파일 정보를 담는 DTO입니다."""

    # 전체 행/컬럼 수와 컬럼별 요약 정보를 함께 전달합니다.
    row_count: int
    column_count: int
    columns: list[DatasetColumnProfile] = Field(default_factory=list)
