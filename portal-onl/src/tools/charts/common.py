from dataclasses import dataclass

import pandas as pd

from features.datasets.application.inspection import build_profile_from_dataframe
from core.utils import read_string
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
from tools.analysis.dataframe_context import load_dataset_dataframe
from tools.dto import ToolExecutionResult


@dataclass(frozen=True, slots=True)
class ChartSpec:
    """선택된 chart id와 렌더링 type을 함께 표현합니다."""

    id: ChartId
    type: str


def read_dataset_id(arguments: dict[str, object]) -> str | None:
    """tool arguments에서 dataset_id를 읽습니다."""
    return read_string(arguments.get("dataset_id"))


def read_analysis_type(arguments: dict[str, object]) -> str:
    """tool arguments에서 analysis_type을 읽고 기본값을 보정합니다."""
    return read_string(arguments.get("analysis_type")) or "dataset_profile"


def read_prompt(arguments: dict[str, object]) -> str | None:
    """tool arguments에서 선택 prompt를 읽습니다."""
    return read_string(arguments.get("prompt"))


def load_dataframe_from_arguments(arguments: dict[str, object]) -> tuple[str, pd.DataFrame]:
    """dataset_id argument로 DataFrame을 로드합니다."""
    dataset_id = read_dataset_id(arguments)
    if dataset_id is None:
        raise ValueError("dataset_id is required.")
    return dataset_id, load_dataset_dataframe(dataset_id)


def build_analytics(
    dataframe: pd.DataFrame,
    analysis_type: str,
    prompt: str | None = None,
) -> AnalyticsPayload:
    """DataFrame과 분석 유형으로 화면 표시용 analytics payload를 생성합니다."""
    return AnalyticsPayload(
        summary_cards=build_summary_cards(dataframe),
        charts=[build_chart(dataframe, analysis_type, prompt)],
        tables=[build_table(dataframe, analysis_type)],
        insights=[build_insight(dataframe, analysis_type, prompt)],
        dataset_profile=build_profile_from_dataframe(dataframe),
    )


def build_summary_cards(dataframe: pd.DataFrame) -> list[SummaryCard]:
    """데이터셋 규모와 품질을 요약하는 카드 목록을 생성합니다."""
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
            value=str(len(numeric_columns(dataframe))),
            detail="Available for trend and correlation analysis",
        ),
        SummaryCard(
            label="Missing Cells",
            value=f"{missing_cells:,}",
            detail="Rows needing attention",
            tone="warning" if missing_cells else "primary",
        ),
    ]


def build_chart(
    dataframe: pd.DataFrame,
    analysis_type: str,
    prompt: str | None = None,
) -> ChartPayload:
    """분석 유형과 데이터 형태에 맞는 단일 chart payload를 생성합니다."""
    spec = select_chart_spec(dataframe, analysis_type, prompt)
    if spec.id == "correlation_scatter":
        return build_correlation_scatter(dataframe)
    if spec.id in {"trend_line", "category_area"}:
        return build_trend_chart(dataframe, chart_id=spec.id, chart_type=spec.type)
    if spec.id == "share_donut":
        return build_share_donut(dataframe)
    return build_category_bar(dataframe)


def select_chart_spec(
    dataframe: pd.DataFrame,
    analysis_type: str,
    prompt: str | None = None,
) -> ChartSpec:
    """분석 유형, prompt, 컬럼 타입을 바탕으로 chart spec을 선택합니다."""
    lowered = (prompt or "").lower()
    numeric = numeric_columns(dataframe)
    datetimes = datetime_columns(dataframe)
    categoricals = categorical_columns(dataframe)

    if analysis_type == "correlation" and len(numeric) > 1:
        return ChartSpec(id="correlation_scatter", type="scatter")
    if analysis_type == "trend":
        if contains_any(lowered, "누적", "volume", "cumulative", "total volume", "총량"):
            return ChartSpec(id="category_area", type="area")
        return ChartSpec(id="trend_line", type="line")
    if contains_any(
        lowered, "비중", "구성", "점유율", "share", "portion", "ratio", "composition"
    ):
        if numeric and categoricals:
            return ChartSpec(id="share_donut", type="donut")
    if analysis_type == "grouped_aggregation" and numeric and categoricals:
        return ChartSpec(id="category_bar", type="bar")
    if datetimes and numeric:
        return ChartSpec(id="trend_line", type="line")
    if numeric and categoricals:
        return ChartSpec(id="category_bar", type="bar")
    if numeric:
        return ChartSpec(id="category_area", type="area")
    return ChartSpec(id="category_bar", type="bar")


def build_correlation_scatter(dataframe: pd.DataFrame) -> ChartPayload:
    """처음 두 숫자형 컬럼으로 correlation scatter chart를 생성합니다."""
    numeric = numeric_columns(dataframe)
    if len(numeric) < 2:
        return build_category_bar(dataframe)

    left = numeric[0]
    right = numeric[1]
    sample = dataframe[[left, right]].dropna().head(48)
    points = [
        ChartPoint(x=float(row[left]), y=float(row[right]), label=f"{index}")
        for index, row in sample.iterrows()
    ]
    return ChartPayload(
        id="correlation_scatter",
        type="scatter",
        title=f"{left.title()} vs {right.title()}",
        points=points,
        meta=ChartMeta(x_label=left, y_label=right),
    )


def build_trend_chart(
    dataframe: pd.DataFrame,
    *,
    chart_id: ChartId = "trend_line",
    chart_type: str = "line",
) -> ChartPayload:
    """숫자형 컬럼과 선택적 날짜 컬럼으로 trend chart를 생성합니다."""
    numeric = numeric_columns(dataframe)
    if not numeric:
        return build_category_bar(dataframe)

    datetimes = datetime_columns(dataframe)
    primary_column = numeric[0]
    sample = dataframe.head(12)
    if datetimes:
        x_labels = [
            value.isoformat() if hasattr(value, "isoformat") else str(value)
            for value in sample[datetimes[0]]
        ]
    else:
        x_labels = [str(index) for index in sample.index]

    return ChartPayload(
        id=chart_id,
        type=chart_type,
        title=f"{primary_column.title()} Trend",
        x=x_labels,
        series=[
            ChartSeries(
                name=primary_column,
                data=[float(value) for value in sample[primary_column].fillna(0)],
            )
        ],
        meta=ChartMeta(
            x_label=datetimes[0] if datetimes else "index",
            y_label=primary_column,
        ),
    )


def build_share_donut(dataframe: pd.DataFrame) -> ChartPayload:
    """범주형 컬럼별 숫자 합계 비중을 donut chart로 생성합니다."""
    numeric = numeric_columns(dataframe)
    categoricals = categorical_columns(dataframe)
    if not numeric or not categoricals:
        return build_category_bar(dataframe)

    category = categoricals[0]
    metric = numeric[0]
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


def build_category_bar(dataframe: pd.DataFrame) -> ChartPayload:
    """범주/숫자 조합 또는 기본 행 분포를 bar chart로 생성합니다."""
    numeric = numeric_columns(dataframe)
    categoricals = categorical_columns(dataframe)
    if numeric and categoricals:
        category = categoricals[0]
        metric = numeric[0]
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
    if numeric:
        primary_column = numeric[0]
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


def build_table(dataframe: pd.DataFrame, analysis_type: str) -> TablePayload:
    """분석 유형에 맞는 표 payload를 생성합니다."""
    numeric = numeric_columns(dataframe)
    categoricals = categorical_columns(dataframe)
    if analysis_type == "anomaly_detection" and numeric:
        return _build_anomaly_table(dataframe, numeric[0])
    if categoricals and numeric:
        return _build_grouped_table(dataframe, categoricals[0], numeric[0])
    return _build_preview_table(dataframe)


def build_insight(
    dataframe: pd.DataFrame,
    analysis_type: str,
    prompt: str | None = None,
) -> InsightPayload:
    """분석 유형과 prompt에 맞는 기본 insight를 생성합니다."""
    numeric = numeric_columns(dataframe)
    categoricals = categorical_columns(dataframe)
    if analysis_type == "correlation" and len(numeric) > 1:
        return InsightPayload(
            title="Correlation Insight",
            body=f"The strongest pairs are derived from {numeric[0]} and the other numeric measures in the uploaded file.",
            action_label="Inspect the strongest relationship",
        )
    if analysis_type == "trend" and numeric:
        return InsightPayload(
            title="Trend Insight",
            body=f"{numeric[0].title()} is available for time-series style tracking across the first rows of the uploaded file.",
            action_label="Review the trend chart",
        )
    if analysis_type == "anomaly_detection" and numeric:
        return InsightPayload(
            title="Anomaly Insight",
            body=f"Potential outliers were calculated from {numeric[0]} using a simple z-score threshold.",
            action_label="Review flagged rows",
        )
    if prompt:
        return InsightPayload(
            title="Prompt-Aligned Insight",
            body=prompt,
            action_label="Refine the question",
        )
    if categoricals:
        return InsightPayload(
            title="Segment Insight",
            body=f"{categoricals[0].title()} looks like a useful segmentation field for the uploaded dataset.",
            action_label="Break down by segment",
        )
    return InsightPayload(
        title="Quality Insight",
        body="The uploaded dataset is ready for profiling and the next step is to inspect missing values or data types.",
        action_label="Profile the dataset",
    )


def inspect_columns(dataframe: pd.DataFrame) -> dict[str, list[str]]:
    """chart 생성에 사용하는 컬럼 타입 분류를 반환합니다."""
    return {
        "numeric_columns": numeric_columns(dataframe),
        "datetime_columns": datetime_columns(dataframe),
        "categorical_columns": categorical_columns(dataframe),
    }


def numeric_columns(dataframe: pd.DataFrame) -> list[str]:
    """DataFrame에서 숫자형 컬럼명을 추출합니다."""
    return [
        column
        for column in dataframe.columns
        if pd.api.types.is_numeric_dtype(dataframe[column])
    ]


def datetime_columns(dataframe: pd.DataFrame) -> list[str]:
    """DataFrame에서 datetime 컬럼명을 추출합니다."""
    return [
        column
        for column in dataframe.columns
        if pd.api.types.is_datetime64_any_dtype(dataframe[column])
    ]


def categorical_columns(dataframe: pd.DataFrame) -> list[str]:
    """DataFrame에서 범주형으로 사용할 수 있는 컬럼명을 추출합니다."""
    return [
        column
        for column in dataframe.columns
        if not pd.api.types.is_numeric_dtype(dataframe[column])
        and not pd.api.types.is_datetime64_any_dtype(dataframe[column])
    ]


def tool_success(data: dict[str, object]) -> dict[str, object]:
    """chart tool 성공 결과를 공통 DTO 형식으로 반환합니다."""
    return ToolExecutionResult[dict[str, object]](ok=True, data=data).model_dump(
        mode="json",
        exclude_none=True,
    )


def tool_error(message: str) -> dict[str, object]:
    """chart tool 실패 결과를 공통 DTO 형식으로 반환합니다."""
    return ToolExecutionResult[object](ok=False, error=message).model_dump(
        mode="json",
        exclude_none=True,
    )


def contains_any(message: str, *keywords: str) -> bool:
    """문자열에 주어진 keyword 중 하나라도 포함되는지 확인합니다."""
    return any(keyword in message for keyword in keywords)


def to_serializable(value: object) -> str | int | float | None:
    """테이블 셀 값을 JSON 직렬화 가능한 형태로 변환합니다."""
    if value is None:
        return None
    if isinstance(value, str | int | float):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _build_anomaly_table(dataframe: pd.DataFrame, column: str) -> TablePayload:
    """z-score 기준 이상치 행 표를 생성합니다."""
    series = dataframe[column].astype(float)
    mean = series.mean()
    std = series.std(ddof=0) or 1.0
    rows: list[dict[str, str | int | float | None]] = []
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


def _build_grouped_table(
    dataframe: pd.DataFrame,
    category: str,
    metric: str,
) -> TablePayload:
    """범주별 count와 평균 표를 생성합니다."""
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


def _build_preview_table(dataframe: pd.DataFrame) -> TablePayload:
    """DataFrame 앞부분을 preview table로 변환합니다."""
    return TablePayload(
        title="Preview Table",
        columns=[
            TableColumn(key=str(column), label=str(column))
            for column in dataframe.columns[:5]
        ],
        rows=[
            {str(column): to_serializable(value) for column, value in row.items()}
            for row in dataframe.head(10).to_dict(orient="records")
        ],
    )
