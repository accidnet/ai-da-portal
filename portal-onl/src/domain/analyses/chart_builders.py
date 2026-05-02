from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from application.datasets.inspection import build_profile_from_dataframe
from domain.shared import (
    AnalyticsPayload,
    ChartId,
    ChartMeta,
    ChartPayload,
    ChartPoint,
    ChartSeries,
    InsightPayload,
    SummaryCard,
    TableColumn,
    TablePayload,
)


@dataclass(frozen=True, slots=True)
class ChartSpec:
    id: ChartId
    type: str


def build_analytics_from_dataframe(
    dataframe: pd.DataFrame, analysis_type: str, prompt: str | None = None
) -> AnalyticsPayload:
    return AnalyticsPayload(
        summary_cards=_build_summary_cards(dataframe),
        charts=[_build_chart(dataframe, analysis_type, prompt)],
        tables=[_build_table(dataframe, analysis_type)],
        insights=[
            _build_insight(dataframe, analysis_type, prompt),
        ],
        dataset_profile=build_profile_from_dataframe(dataframe),
    )


def _build_summary_cards(dataframe: pd.DataFrame) -> list[SummaryCard]:
    numeric_columns = [
        column
        for column in dataframe.columns
        if pd.api.types.is_numeric_dtype(dataframe[column])
    ]
    missing_cells = int(dataframe.isna().sum().sum())
    return [
        SummaryCard(
            label="Rows",
            value=f"{len(dataframe):,}",
            detail="Loaded from the uploaded file",
        ),
        SummaryCard(
            label="Columns",
            value=str(len(dataframe.columns)),
            detail="Detected in dataframe",
        ),
        SummaryCard(
            label="Numeric Columns",
            value=str(len(numeric_columns)),
            detail="Available for trend and correlation analysis",
        ),
        SummaryCard(
            label="Missing Cells",
            value=f"{missing_cells:,}",
            detail="Rows needing attention",
            tone="warning" if missing_cells else "primary",
        ),
    ]


def _build_chart(
    dataframe: pd.DataFrame, analysis_type: str, prompt: str | None
) -> ChartPayload:
    spec = _select_chart_spec(dataframe, analysis_type, prompt)

    if spec.id == "correlation_scatter":
        return _build_correlation_scatter(dataframe)
    if spec.id == "trend_line":
        return _build_trend_chart(dataframe, chart_id=spec.id, chart_type=spec.type)
    if spec.id == "category_area":
        return _build_trend_chart(dataframe, chart_id=spec.id, chart_type=spec.type)
    if spec.id == "share_donut":
        return _build_share_donut(dataframe)
    return _build_category_bar(dataframe)


def _select_chart_spec(
    dataframe: pd.DataFrame, analysis_type: str, prompt: str | None
) -> ChartSpec:
    lowered = (prompt or "").lower()
    numeric_columns = _numeric_columns(dataframe)
    datetime_columns = _datetime_columns(dataframe)
    categorical_columns = _categorical_columns(dataframe)

    if analysis_type == "correlation" and len(numeric_columns) > 1:
        return ChartSpec(id="correlation_scatter", type="scatter")

    if analysis_type == "trend":
        if _contains_any(
            lowered, "누적", "volume", "cumulative", "total volume", "총량"
        ):
            return ChartSpec(id="category_area", type="area")
        return ChartSpec(id="trend_line", type="line")

    if _contains_any(
        lowered, "비중", "구성", "점유율", "share", "portion", "ratio", "composition"
    ):
        if numeric_columns and categorical_columns:
            return ChartSpec(id="share_donut", type="donut")

    if (
        analysis_type == "grouped_aggregation"
        and numeric_columns
        and categorical_columns
    ):
        return ChartSpec(id="category_bar", type="bar")

    if datetime_columns and numeric_columns:
        return ChartSpec(id="trend_line", type="line")

    if numeric_columns and categorical_columns:
        return ChartSpec(id="category_bar", type="bar")

    if numeric_columns:
        return ChartSpec(id="category_area", type="area")

    return ChartSpec(id="category_bar", type="bar")


def _build_correlation_scatter(dataframe: pd.DataFrame) -> ChartPayload:
    numeric_columns = _numeric_columns(dataframe)
    if len(numeric_columns) < 2:
        return _build_category_bar(dataframe)

    left = numeric_columns[0]
    right = numeric_columns[1]
    sample = dataframe[[left, right]].dropna().head(48)
    points = [
        ChartPoint(
            x=float(row[left]),
            y=float(row[right]),
            label=f"{index}",
        )
        for index, row in sample.iterrows()
    ]
    return ChartPayload(
        id="correlation_scatter",
        type="scatter",
        title=f"{left.title()} vs {right.title()}",
        points=points,
        meta=ChartMeta(x_label=left, y_label=right),
    )


def _build_trend_chart(
    dataframe: pd.DataFrame, *, chart_id: ChartId, chart_type: str
) -> ChartPayload:
    numeric_columns = _numeric_columns(dataframe)
    if not numeric_columns:
        return _build_category_bar(dataframe)

    datetime_columns = _datetime_columns(dataframe)
    primary_column = numeric_columns[0]
    sample = dataframe.head(12)

    if datetime_columns:
        x_labels = [
            value.isoformat() if hasattr(value, "isoformat") else str(value)
            for value in sample[datetime_columns[0]]
        ]
    else:
        x_labels = [str(index) for index in sample.index]

    series_data = [float(value) for value in sample[primary_column].fillna(0)]
    return ChartPayload(
        id=chart_id,
        type=chart_type,
        title=f"{primary_column.title()} Trend",
        x=x_labels,
        series=[ChartSeries(name=primary_column, data=series_data)],
        meta=ChartMeta(
            x_label=datetime_columns[0] if datetime_columns else "index",
            y_label=primary_column,
        ),
    )


def _build_share_donut(dataframe: pd.DataFrame) -> ChartPayload:
    numeric_columns = _numeric_columns(dataframe)
    categorical_columns = _categorical_columns(dataframe)
    if not numeric_columns or not categorical_columns:
        return _build_category_bar(dataframe)

    category = categorical_columns[0]
    metric = numeric_columns[0]
    grouped = (
        dataframe[[category, metric]]
        .dropna()
        .groupby(category, as_index=False)[metric]
        .sum()
        .sort_values(metric, ascending=False)
        .head(6)
    )
    return ChartPayload(
        id="share_donut",
        type="donut",
        title=f"{metric.title()} Share by {category.title()}",
        x=[str(value) for value in grouped[category]],
        series=[
            ChartSeries(
                name=metric,
                data=[round(float(value), 4) for value in grouped[metric]],
            )
        ],
        meta=ChartMeta(x_label=category, y_label=metric),
    )


def _build_category_bar(dataframe: pd.DataFrame) -> ChartPayload:
    numeric_columns = _numeric_columns(dataframe)
    categorical_columns = _categorical_columns(dataframe)

    if numeric_columns and categorical_columns:
        category = categorical_columns[0]
        metric = numeric_columns[0]
        grouped = (
            dataframe[[category, metric]]
            .dropna()
            .groupby(category, as_index=False)[metric]
            .sum()
            .sort_values(metric, ascending=False)
            .head(8)
        )
        return ChartPayload(
            id="category_bar",
            type="bar",
            title=f"{metric.title()} by {category.title()}",
            x=[str(value) for value in grouped[category]],
            series=[
                ChartSeries(
                    name=metric,
                    data=[round(float(value), 4) for value in grouped[metric]],
                )
            ],
            meta=ChartMeta(x_label=category, y_label=metric),
        )

    if numeric_columns:
        primary_column = numeric_columns[0]
        sample = dataframe[primary_column].head(8).fillna(0)
        return ChartPayload(
            id="category_bar",
            type="bar",
            title=f"{primary_column.title()} Distribution",
            x=[str(index) for index in sample.index],
            series=[
                ChartSeries(
                    name=primary_column,
                    data=[float(value) for value in sample],
                )
            ],
            meta=ChartMeta(x_label="index", y_label=primary_column),
        )

    sample_size = min(len(dataframe), 5)
    return ChartPayload(
        id="category_bar",
        type="bar",
        title="Row Distribution",
        x=[str(index) for index in range(sample_size)],
        series=[ChartSeries(name="records", data=[1 for _ in range(sample_size)])],
        meta=ChartMeta(x_label="row", y_label="records"),
    )


def _build_table(dataframe: pd.DataFrame, analysis_type: str) -> TablePayload:
    numeric_columns = _numeric_columns(dataframe)
    categorical_columns = _categorical_columns(dataframe)

    if analysis_type == "anomaly_detection" and numeric_columns:
        column = numeric_columns[0]
        series = dataframe[column].astype(float)
        mean = series.mean()
        std = series.std(ddof=0) or 1.0
        rows = []
        for index, value in series.items():
            z_score = abs((value - mean) / std)
            if z_score >= 2:
                rows.append(
                    {
                        "row": str(index),
                        "value": round(float(value), 4),
                        "z_score": round(float(z_score), 2),
                    }
                )
        return TablePayload(
            title=f"Anomalies in {column}",
            columns=[
                TableColumn(key="row", label="Row"),
                TableColumn(key="value", label="Value"),
                TableColumn(key="z_score", label="Z Score"),
            ],
            rows=rows[:10],
        )

    if categorical_columns and numeric_columns:
        category = categorical_columns[0]
        metric = numeric_columns[0]
        grouped = (
            dataframe[[category, metric]]
            .dropna()
            .groupby(category, as_index=False)
            .agg({metric: ["count", "mean"]})
        )
        grouped.columns = [category, "count", "mean"]
        return TablePayload(
            title=f"Grouped View by {category.title()}",
            columns=[
                TableColumn(key=category, label=category.title()),
                TableColumn(key="count", label="Count"),
                TableColumn(key="mean", label=f"Avg {metric}"),
            ],
            rows=[
                {
                    category: str(row[category]),
                    "count": int(row["count"]),
                    "mean": round(float(row["mean"]), 4),
                }
                for _, row in grouped.head(10).iterrows()
            ],
        )

    return TablePayload(
        title="Preview Table",
        columns=[
            TableColumn(key=str(column), label=str(column))
            for column in dataframe.columns[:5]
        ],
        rows=[
            {str(column): _to_serializable(value) for column, value in row.items()}
            for row in dataframe.head(10).to_dict(orient="records")
        ],
    )


def _build_insight(
    dataframe: pd.DataFrame, analysis_type: str, prompt: str | None
) -> InsightPayload:
    numeric_columns = _numeric_columns(dataframe)
    categorical_columns = _categorical_columns(dataframe)

    if analysis_type == "correlation" and len(numeric_columns) > 1:
        return InsightPayload(
            title="Correlation Insight",
            body=f"The strongest pairs are derived from {numeric_columns[0]} and the other numeric measures in the uploaded file.",
            action_label="Inspect the strongest relationship",
        )

    if analysis_type == "trend" and numeric_columns:
        return InsightPayload(
            title="Trend Insight",
            body=f"{numeric_columns[0].title()} is available for time-series style tracking across the first rows of the uploaded file.",
            action_label="Review the trend chart",
        )

    if analysis_type == "anomaly_detection" and numeric_columns:
        return InsightPayload(
            title="Anomaly Insight",
            body=f"Potential outliers were calculated from {numeric_columns[0]} using a simple z-score threshold.",
            action_label="Review flagged rows",
        )

    if prompt:
        return InsightPayload(
            title="Prompt-Aligned Insight",
            body=prompt,
            action_label="Refine the question",
        )

    if categorical_columns:
        return InsightPayload(
            title="Segment Insight",
            body=f"{categorical_columns[0].title()} looks like a useful segmentation field for the uploaded dataset.",
            action_label="Break down by segment",
        )

    return InsightPayload(
        title="Quality Insight",
        body="The uploaded dataset is ready for profiling and the next step is to inspect missing values or data types.",
        action_label="Profile the dataset",
    )


def _numeric_columns(dataframe: pd.DataFrame) -> list[str]:
    return [
        column
        for column in dataframe.columns
        if pd.api.types.is_numeric_dtype(dataframe[column])
    ]


def _datetime_columns(dataframe: pd.DataFrame) -> list[str]:
    return [
        column
        for column in dataframe.columns
        if pd.api.types.is_datetime64_any_dtype(dataframe[column])
    ]


def _categorical_columns(dataframe: pd.DataFrame) -> list[str]:
    return [
        column
        for column in dataframe.columns
        if not pd.api.types.is_numeric_dtype(dataframe[column])
        and not pd.api.types.is_datetime64_any_dtype(dataframe[column])
    ]


def _contains_any(message: str, *keywords: str) -> bool:
    return any(keyword in message for keyword in keywords)


def _to_serializable(value: object) -> str | int | float | None:
    if value is None:
        return None
    if isinstance(value, (str, int, float)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
