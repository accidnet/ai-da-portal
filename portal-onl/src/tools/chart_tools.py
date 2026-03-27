from domain.shared import ChartPayload, ChartSeries


def line_chart(
    title: str, x: list[str], name: str, data: list[float | int]
) -> ChartPayload:
    return ChartPayload(
        type="line", title=title, x=x, series=[ChartSeries(name=name, data=data)]
    )
