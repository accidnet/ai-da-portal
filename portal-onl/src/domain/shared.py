from typing import Literal

from pydantic import BaseModel, Field

from features.datasets.application.dto import DatasetProfilePayload


ReasoningStatus = Literal[
    "queued", "profiling", "running_analysis", "completed", "failed"
]
ChartType = Literal["line", "bar", "area", "scatter", "donut", "table", "metric"]
ChartId = Literal[
    "trend_line",
    "category_bar",
    "category_area",
    "correlation_scatter",
    "share_donut",
]
WorkspaceTemplateId = Literal[
    "overview",
    "chart_focus",
    "table_focus",
    "dataset_profile",
    "executive_summary",
    "correlation_focus",
    "trend_story",
    "anomaly_watch",
    "comparison_board",
]
WorkspaceSectionKind = Literal[
    "summary_cards",
    "chart",
    "table",
    "insight",
    "dataset_profile",
]


class SummaryCard(BaseModel):
    label: str
    value: str
    detail: str | None = None
    tone: Literal["primary", "warning", "neutral"] = "primary"


class ChartSeries(BaseModel):
    name: str
    data: list[float | int | str | None]


class ChartPoint(BaseModel):
    x: float
    y: float
    label: str | None = None


class ChartMeta(BaseModel):
    x_label: str | None = None
    y_label: str | None = None


class ChartPayload(BaseModel):
    id: ChartId | None = None
    type: ChartType
    title: str
    x: list[str] = Field(default_factory=list)
    series: list[ChartSeries] = Field(default_factory=list)
    points: list[ChartPoint] = Field(default_factory=list)
    meta: ChartMeta | None = None


class TableColumn(BaseModel):
    key: str
    label: str


class TablePayload(BaseModel):
    title: str
    columns: list[TableColumn]
    rows: list[dict[str, str | int | float | None]]


class InsightPayload(BaseModel):
    title: str
    body: str
    action_label: str | None = None


class AnalyticsPayload(BaseModel):
    summary_cards: list[SummaryCard] = Field(default_factory=list)
    charts: list[ChartPayload] = Field(default_factory=list)
    tables: list[TablePayload] = Field(default_factory=list)
    insights: list[InsightPayload] = Field(default_factory=list)
    dataset_profile: DatasetProfilePayload | None = None


class WorkspaceSectionPayload(BaseModel):
    kind: WorkspaceSectionKind
    title: str | None = None
    chart_index: int | None = None
    table_index: int | None = None
    insight_index: int | None = None
    max_items: int | None = None
    summary_card_labels: list[str] = Field(default_factory=list)


class WorkspacePayload(BaseModel):
    template_id: WorkspaceTemplateId
    title: str
    description: str | None = None
    sections: list[WorkspaceSectionPayload] = Field(default_factory=list)
