from __future__ import annotations

from itertools import combinations

import pandas as pd

from domain.shared import (
    AnalyticsPayload,
    ChartPayload,
    ChartSeries,
    InsightPayload,
    SummaryCard,
    TableColumn,
    TablePayload,
)


def build_analytics_from_dataframe(
    dataframe: pd.DataFrame, analysis_type: str, prompt: str | None = None
) -> AnalyticsPayload:
    return AnalyticsPayload(
        summary_cards=_build_summary_cards(dataframe),
        charts=[_build_chart(dataframe, analysis_type)],
        tables=[_build_table(dataframe, analysis_type)],
        insights=[
            _build_insight(dataframe, analysis_type, prompt),
        ],
        dataset_profile=None,
    )


def _build_summary_cards(dataframe: pd.DataFrame) -> list[SummaryCard]:
    numeric_columns = [
        column for column in dataframe.columns if pd.api.types.is_numeric_dtype(dataframe[column])
    ]
    missing_cells = int(dataframe.isna().sum().sum())
    return [
        SummaryCard(label="Rows", value=f"{len(dataframe):,}", detail="Loaded from the uploaded file"),
        SummaryCard(label="Columns", value=str(len(dataframe.columns)), detail="Detected in dataframe"),
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


def _build_chart(dataframe: pd.DataFrame, analysis_type: str) -> ChartPayload:
    numeric_columns = [
        column for column in dataframe.columns if pd.api.types.is_numeric_dtype(dataframe[column])
    ]
    datetime_columns = [
        column
        for column in dataframe.columns
        if pd.api.types.is_datetime64_any_dtype(dataframe[column])
    ]
    if not numeric_columns:
        return ChartPayload(
            type="bar",
            title="No numeric columns available",
            x=[str(index) for index in range(min(len(dataframe), 5))],
            series=[ChartSeries(name="records", data=[1 for _ in range(min(len(dataframe), 5))])],
        )

    primary_column = numeric_columns[0]
    if analysis_type == "correlation" and len(numeric_columns) > 1:
        x_labels: list[str] = []
        series_data: list[float] = []
        for left, right in combinations(numeric_columns, 2):
            x_labels.append(f"{left} vs {right}")
            series_data.append(float(dataframe[left].corr(dataframe[right]) or 0.0))
        return ChartPayload(
            type="bar",
            title="Correlation Strength",
            x=x_labels[:8],
            series=[ChartSeries(name="correlation", data=series_data[:8])],
        )

    if analysis_type == "trend":
        if datetime_columns:
            x_labels = [
                value.isoformat() if hasattr(value, "isoformat") else str(value)
                for value in dataframe[datetime_columns[0]].head(12)
            ]
        else:
            x_labels = [str(index) for index in dataframe.index[:12]]
        series_data = [float(value) for value in dataframe[primary_column].head(12).fillna(0)]
        return ChartPayload(
            type="line",
            title=f"{primary_column.title()} Trend",
            x=x_labels,
            series=[ChartSeries(name=primary_column, data=series_data)],
        )

    grouped = dataframe[primary_column].head(10)
    return ChartPayload(
        type="bar",
        title=f"{primary_column.title()} Distribution",
        x=[str(value) for value in grouped.index],
        series=[ChartSeries(name=primary_column, data=[float(value) for value in grouped.fillna(0)])],
    )


def _build_table(dataframe: pd.DataFrame, analysis_type: str) -> TablePayload:
    numeric_columns = [
        column for column in dataframe.columns if pd.api.types.is_numeric_dtype(dataframe[column])
    ]
    categorical_columns = [
        column for column in dataframe.columns if not pd.api.types.is_numeric_dtype(dataframe[column])
    ]

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
        columns=[TableColumn(key=str(column), label=str(column)) for column in dataframe.columns[:5]],
        rows=[
            {str(column): _to_serializable(value) for column, value in row.items()}
            for row in dataframe.head(10).to_dict(orient="records")
        ],
    )


def _build_insight(
    dataframe: pd.DataFrame, analysis_type: str, prompt: str | None
) -> InsightPayload:
    numeric_columns = [
        column for column in dataframe.columns if pd.api.types.is_numeric_dtype(dataframe[column])
    ]
    categorical_columns = [
        column for column in dataframe.columns if not pd.api.types.is_numeric_dtype(dataframe[column])
    ]
    missing_cells = int(dataframe.isna().sum().sum())

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


def _to_serializable(value: object) -> str | int | float | None:
    if value is None:
        return None
    if isinstance(value, (str, int, float)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
