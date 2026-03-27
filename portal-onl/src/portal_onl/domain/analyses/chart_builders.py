from portal_onl.domain.shared import (
    ChartPayload,
    ChartSeries,
    SummaryCard,
    TableColumn,
    TablePayload,
)


def build_demo_chart(title: str) -> ChartPayload:
    return ChartPayload(
        type="bar",
        title=title,
        x=["Jan", "Feb", "Mar"],
        series=[ChartSeries(name="new_users", data=[120, 148, 166])],
    )


def build_demo_cards() -> list[SummaryCard]:
    return [
        SummaryCard(label="Rows", value="1.2K"),
        SummaryCard(label="Numeric Columns", value="3"),
    ]


def build_demo_table() -> TablePayload:
    return TablePayload(
        title="Channel Snapshot",
        columns=[
            TableColumn(key="channel", label="Channel"),
            TableColumn(key="roi", label="ROI"),
        ],
        rows=[
            {"channel": "Social", "roi": "4.2x"},
            {"channel": "Search", "roi": "2.8x"},
        ],
    )
