from typing import Literal

from pydantic import BaseModel, Field

from features.datasets.application.dto import DatasetProfilePayload


ChartType = Literal[
    "line",
    "bar",
    "area",
    "scatter",
    "bubble",
    "histogram",
    "donut",
    "table",
    "metric",
]
ChartId = Literal[
    "trend_line",
    "category_bar",
    "category_area",
    "correlation_scatter",
    "segment_bubble",
    "distribution_histogram",
    "share_donut",
]


class SummaryCard(BaseModel):
    """분석 결과 상단에 표시할 요약 카드 payload입니다."""

    label: str
    value: str
    detail: str | None = None
    tone: Literal["primary", "warning", "neutral"] = "primary"


class ChartSeries(BaseModel):
    """축 기반 차트에서 사용하는 series payload입니다."""

    name: str
    data: list[float | int | str | None]


class ChartPoint(BaseModel):
    """scatter/bubble 차트에서 사용하는 point payload입니다."""

    x: float
    y: float
    label: str | None = None
    size: float | None = None
    category: str | None = None


class ChartMeta(BaseModel):
    """차트 축 제목 등 렌더링 보조 메타데이터입니다."""

    x_label: str | None = None
    y_label: str | None = None


class ChartPayload(BaseModel):
    """프론트 차트 렌더러가 소비하는 공통 차트 payload입니다."""

    id: ChartId | None = None
    type: ChartType
    title: str
    x: list[str] = Field(default_factory=list)
    series: list[ChartSeries] = Field(default_factory=list)
    points: list[ChartPoint] = Field(default_factory=list)
    meta: ChartMeta | None = None


class TableColumn(BaseModel):
    """분석 테이블의 컬럼 표시 정보를 표현합니다."""

    key: str
    label: str


class TablePayload(BaseModel):
    """프론트 테이블 렌더러가 소비하는 분석 테이블 payload입니다."""

    title: str
    columns: list[TableColumn]
    rows: list[dict[str, str | int | float | None]]


class InsightPayload(BaseModel):
    """분석 결과에서 보여줄 단일 인사이트 payload입니다."""

    title: str
    body: str
    action_label: str | None = None


class AnalyticsPayload(BaseModel):
    """차트, 테이블, 인사이트를 묶은 분석 화면 payload입니다."""

    summary_cards: list[SummaryCard] = Field(default_factory=list)
    charts: list[ChartPayload] = Field(default_factory=list)
    tables: list[TablePayload] = Field(default_factory=list)
    insights: list[InsightPayload] = Field(default_factory=list)
    dataset_profile: DatasetProfilePayload | None = None
