# visualizations

`AnalysisVisualizationPane.vue`에서 사용하는 차트 컴포넌트입니다. ECharts 인스턴스 생명주기는 `EChartRenderer.vue`가 담당하고, 차트별 option 생성은 `chartOptions.ts`가 담당합니다. `LineTrend.vue`, `BarChart.vue`, `AreaTrend.vue`, `ScatterPlot.vue`, `HistogramChart.vue`, `DonutShare.vue`, `BarLine.vue`는 chart id/type에 맞는 얇은 래퍼입니다.

## 선택 규칙

- `resolveVisualizationComponent(chart)`는 `chart.id`를 먼저 보고, 없으면 `chart.type`을 사용합니다.
- 지원 id:
  - `trend_line` -> `LineTrend.vue`
  - `category_bar` -> `BarChart.vue`
  - `category_area` -> `AreaTrend.vue`
  - `correlation_scatter` -> `ScatterPlot.vue`
  - `segment_bubble` -> `ScatterPlot.vue`
  - `distribution_histogram` -> `HistogramChart.vue`
  - `share_donut` -> `DonutShare.vue`
- 지원 type:
  - `line`, `bar`, `area`, `scatter`, `bubble`, `histogram`, `donut`
- id/type이 매칭되지 않으면 `BarLine.vue`가 fallback으로 렌더링됩니다.

## 백엔드 chart payload

프론트는 `AnalyticsChartPayload` 형태를 기대합니다.

```ts
interface AnalyticsChartPayload {
  id?: 'trend_line' | 'category_bar' | 'category_area' | 'correlation_scatter' | 'segment_bubble' | 'distribution_histogram' | 'share_donut' | null
  type: 'line' | 'bar' | 'area' | 'scatter' | 'bubble' | 'histogram' | 'donut' | 'table' | 'metric'
  title: string
  x: string[]
  series: Array<{
    name: string
    data: Array<number | string | null>
  }>
  points?: Array<{
    x: number
    y: number
    label?: string | null
    size?: number | null
    category?: string | null
  }>
  meta?: {
    x_label?: string | null
    y_label?: string | null
  } | null
}
```

## 차트별 데이터 규칙

### Line, Area, Bar

- `x`는 x축 category label 배열입니다.
- `series`는 하나 이상 전달할 수 있습니다.
- 각 `series.data[index]`는 `x[index]`에 대응합니다.
- 숫자 문자열은 프론트에서 숫자로 변환합니다. 숫자로 변환되지 않는 문자열은 ECharts에 그대로 전달합니다.

예시:

```json
{
  "id": "trend_line",
  "type": "line",
  "title": "월별 매출 추이",
  "x": ["2026-01", "2026-02"],
  "series": [{ "name": "sales", "data": [1200, 1800] }],
  "meta": { "x_label": "month", "y_label": "sales" }
}
```

### Scatter

- `points`를 사용합니다.
- `points[].x`, `points[].y`는 숫자여야 합니다.
- `series`와 `x`는 빈 배열이어도 됩니다.

예시:

```json
{
  "id": "correlation_scatter",
  "type": "scatter",
  "title": "객단가와 재구매율",
  "x": [],
  "series": [],
  "points": [
    { "x": 12000, "y": 0.24, "label": "A" },
    { "x": 18000, "y": 0.31, "label": "B" }
  ],
  "meta": { "x_label": "avg_order_value", "y_label": "repurchase_rate" }
}
```

### Bubble

- `points`를 사용합니다.
- `points[].x`, `points[].y`는 좌표이고, `points[].size`는 버블 크기입니다.
- `points[].category`가 있으면 category별 series와 legend로 나뉩니다.
- ECharts에서는 scatter series의 `symbolSize`로 버블 크기를 표현합니다.

예시:

```json
{
  "id": "segment_bubble",
  "type": "bubble",
  "title": "세그먼트 규모와 전환율",
  "x": [],
  "series": [],
  "points": [
    { "x": 12000, "y": 0.24, "size": 340, "label": "A", "category": "신규" },
    { "x": 18000, "y": 0.31, "size": 520, "label": "B", "category": "기존" }
  ],
  "meta": { "x_label": "avg_order_value", "y_label": "conversion_rate" }
}
```

### Histogram

- `x`는 bin label 배열입니다.
- `series[0].data`는 각 bin의 빈도입니다.
- 프론트는 histogram 전용 option을 사용해 bin 간격을 좁힌 bar 형태로 렌더링합니다.

예시:

```json
{
  "id": "distribution_histogram",
  "type": "histogram",
  "title": "매출 분포",
  "x": ["0 - 100", "100 - 200", "200 - 300"],
  "series": [{ "name": "frequency", "data": [4, 12, 6] }],
  "meta": { "x_label": "sales", "y_label": "frequency" }
}
```

### Donut

- `x`는 segment label 배열입니다.
- `series[0].data`는 각 segment의 값입니다.
- `x[index]`와 `series[0].data[index]`가 대응합니다.

예시:

```json
{
  "id": "share_donut",
  "type": "donut",
  "title": "채널별 매출 비중",
  "x": ["검색", "광고", "추천"],
  "series": [{ "name": "revenue", "data": [45, 32, 23] }]
}
```

## 렌더링 메모

- `EChartRenderer.vue`는 `ResizeObserver`로 패널 크기 변경 시 `resize()`를 호출합니다.
- 렌더러는 chart data가 없을 때 상위 화면의 fallback point를 `bar_line` 형태로 표시합니다.
- 백엔드에서 실시간 SSE `agent.iteration.chart`로 chart payload를 보내면 `analyticsPayload.charts`에 즉시 반영됩니다.
