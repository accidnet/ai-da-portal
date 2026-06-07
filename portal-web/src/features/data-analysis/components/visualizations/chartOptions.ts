import type { EChartsCoreOption as EChartsOption } from 'echarts/core'

import type { AnalyticsChartPayload, AnalyticsChartType, ChartPoint } from '@/features/data-analysis/types'

export type ChartRendererType = AnalyticsChartType | 'bar_line'

type TooltipParam = { data?: unknown; name?: string; axisValueLabel?: string }
type CategoryAxisLabelLayout = {
  rotate: number
  interval: number | 'auto'
  width: number
  gridBottom: number
}
type ChartGridLayout = {
  bottom: number
  left: number
}
type ValueAxisLayout = ChartGridLayout & {
  xNameGap: number
  yNameGap: number
}

/** 차트 payload와 강제 타입을 기준으로 ECharts option을 생성합니다. */
export function buildChartOption(
  chart: AnalyticsChartPayload | null,
  chartType: ChartRendererType | undefined,
  fallbackPoints: ChartPoint[],
): EChartsOption {
  const resolvedType = chartType ?? chart?.type ?? 'bar_line'
  if (!chart || !hasRenderableData(chart)) {
    return buildFallbackOption(fallbackPoints)
  }
  if (resolvedType === 'bubble') return buildBubbleOption(chart)
  if (resolvedType === 'scatter') return buildScatterOption(chart)
  if (resolvedType === 'donut') return buildDonutOption(chart)
  if (resolvedType === 'area') return buildAxisOption(chart, 'line', true)
  if (resolvedType === 'histogram') return buildHistogramOption(chart)
  if (resolvedType === 'line') return buildAxisOption(chart, 'line', false)
  if (resolvedType === 'bar') return buildAxisOption(chart, 'bar', false)
  return buildBarLineOption(chart)
}

/** points 또는 series 중 렌더링 가능한 데이터가 있는지 확인합니다. */
function hasRenderableData(chart: AnalyticsChartPayload | null): boolean {
  if (!chart) return false
  if (chart.points?.length) return true
  return chart.series.some((series) => series.data.length > 0)
}

/** 모든 차트가 공유하는 기본 색상, 툴팁, grid 설정을 제공합니다. */
function buildBaseOption(gridLayout: Partial<ChartGridLayout> = {}): EChartsOption {
  return {
    color: ['#184a8c', '#3c78c9', '#7a9cc9', '#a8bdd7', '#d7a43a', '#6f7d8f'],
    animationDuration: 260,
    textStyle: {
      color: '#334155',
      fontFamily: 'Inter, Pretendard, system-ui, sans-serif',
    },
    tooltip: {
      trigger: 'axis',
      confine: true,
      backgroundColor: 'rgba(15, 23, 42, 0.92)',
      borderWidth: 0,
      textStyle: { color: '#fff' },
    },
    grid: {
      top: 28,
      right: 18,
      bottom: gridLayout.bottom ?? 48,
      left: gridLayout.left ?? 44,
      containLabel: true,
    },
  }
}

/** line, area, bar처럼 category x축을 쓰는 차트 option을 생성합니다. */
function buildAxisOption(chart: AnalyticsChartPayload, type: 'line' | 'bar', isArea: boolean): EChartsOption {
  const xAxisLabelLayout = resolveCategoryAxisLabelLayout(chart.x)
  const gridLayout = resolveGridLayout({
    xAxisLabelLayout,
    hasXAxisName: Boolean(chart.meta?.x_label),
    hasYAxisName: Boolean(chart.meta?.y_label),
  })
  return {
    ...buildBaseOption(gridLayout),
    xAxis: {
      type: 'category',
      data: chart.x,
      name: chart.meta?.x_label ?? undefined,
      nameGap: xAxisLabelLayout.rotate ? 58 : 40,
      nameLocation: 'middle',
      nameTextStyle: { color: '#475569', fontWeight: 700 },
      boundaryGap: type === 'bar',
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#cbd5e1' } },
      axisLabel: {
        color: '#64748b',
        hideOverlap: true,
        interval: xAxisLabelLayout.interval,
        overflow: 'truncate',
        rotate: xAxisLabelLayout.rotate,
        width: xAxisLabelLayout.width,
      },
    },
    yAxis: {
      type: 'value',
      name: chart.meta?.y_label ?? undefined,
      nameGap: 82,
      nameLocation: 'middle',
      nameRotate: 90,
      nameTextStyle: { color: '#475569', fontWeight: 700 },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.2)' } },
      axisLabel: { color: '#64748b', margin: 10 },
    },
    series: chart.series.map((series) => ({
      name: series.name,
      type,
      data: series.data.map(normalizeAxisValue),
      smooth: type === 'line',
      symbol: type === 'line' ? 'circle' : 'none',
      symbolSize: 6,
      areaStyle: isArea ? { opacity: 0.16 } : undefined,
      lineStyle: type === 'line' ? { width: 3 } : undefined,
      barMaxWidth: type === 'bar' ? 34 : undefined,
      itemStyle: type === 'bar' ? { borderRadius: [8, 8, 2, 2] } : undefined,
    })),
  }
}

/** 축 제목과 x축 라벨 영역이 겹치지 않도록 grid 여백을 계산합니다. */
function resolveGridLayout({
  xAxisLabelLayout,
  hasXAxisName,
  hasYAxisName,
}: {
  xAxisLabelLayout: CategoryAxisLabelLayout
  hasXAxisName: boolean
  hasYAxisName: boolean
}): ChartGridLayout {
  return {
    // 축 제목을 중앙에 배치할 때 라벨과 겹치지 않도록 축 제목 공간을 별도로 확보합니다.
    bottom: xAxisLabelLayout.gridBottom + (hasXAxisName ? 24 : 0),
    left: hasYAxisName ? 92 : 44,
  }
}

/** x축 라벨 개수와 길이에 따라 회전, 간격, 하단 여백을 결정합니다. */
function resolveCategoryAxisLabelLayout(labels: string[]): CategoryAxisLabelLayout {
  const longestLabelLength = labels.reduce((maxLength, label) => Math.max(maxLength, String(label).length), 0)
  const hasDenseLabels = labels.length > 8
  const hasLongLabels = longestLabelLength > 10

  if (hasLongLabels || hasDenseLabels) {
    // 좁은 analytics 패널에서 긴 x축 라벨이 캔버스 밖으로 잘리지 않도록 회전과 하단 여백을 함께 늘립니다.
    return {
      rotate: 35,
      interval: labels.length > 14 ? 'auto' : 0,
      width: 92,
      gridBottom: 76,
    }
  }

  return {
    rotate: 0,
    interval: 0,
    width: 80,
    gridBottom: 48,
  }
}

/** 기본 fallback과 혼합형 차트에서 쓰는 bar + trend line option을 생성합니다. */
function buildBarLineOption(chart: AnalyticsChartPayload): EChartsOption {
  const base = buildAxisOption(chart, 'bar', false)
  const firstSeries = chart.series[0]
  if (!firstSeries) return base

  return {
    ...base,
    series: [
      {
        name: firstSeries.name,
        type: 'bar',
        data: firstSeries.data.map(normalizeAxisValue),
        barMaxWidth: 34,
        itemStyle: { borderRadius: [8, 8, 2, 2] },
      },
      {
        name: `${firstSeries.name} trend`,
        type: 'line',
        data: firstSeries.data.map(normalizeAxisValue),
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 3 },
      },
    ],
  }
}

/** bin label과 빈도 series를 히스토그램 막대로 표현합니다. */
function buildHistogramOption(chart: AnalyticsChartPayload): EChartsOption {
  const option = buildAxisOption(chart, 'bar', false)
  return {
    ...option,
    tooltip: {
      trigger: 'axis',
      confine: true,
      backgroundColor: 'rgba(15, 23, 42, 0.92)',
      borderWidth: 0,
      textStyle: { color: '#fff' },
      formatter(params: TooltipParam | TooltipParam[]) {
        const items = Array.isArray(params) ? params : [params]
        const first = items[0]
        const binLabel = first?.axisValueLabel ?? first?.name ?? '-'
        const frequency = Array.isArray(first?.data) ? first?.data[1] : first?.data ?? '-'
        return `${chart.meta?.x_label ?? 'bin'}: ${binLabel}<br/>빈도: ${frequency}`
      },
    },
    series: chart.series.map((series) => ({
      name: series.name,
      type: 'bar',
      data: series.data.map(normalizeAxisValue),
      barCategoryGap: '4%',
      barGap: '0%',
      itemStyle: { borderRadius: [4, 4, 0, 0] },
    })),
  }
}

/** x/y points를 고정 크기 scatter series로 변환합니다. */
function buildScatterOption(chart: AnalyticsChartPayload): EChartsOption {
  const axisLayout = resolveValueAxisLayout(chart)

  return {
    ...buildBaseOption(axisLayout),
    tooltip: {
      trigger: 'item',
      confine: true,
      backgroundColor: 'rgba(15, 23, 42, 0.92)',
      borderWidth: 0,
      textStyle: { color: '#fff' },
      formatter(params: TooltipParam | TooltipParam[]) {
        if (Array.isArray(params)) return ''
        const data = Array.isArray(params.data) ? params.data : []
        const label = data[2] ? `${data[2]}<br/>` : ''
        return `${label}${chart.meta?.x_label ?? 'x'}: ${data[0]}<br/>${chart.meta?.y_label ?? 'y'}: ${data[1]}`
      },
    },
    xAxis: buildValueXAxis(chart, axisLayout),
    yAxis: buildValueYAxis(chart, axisLayout),
    series: [
      {
        name: chart.title,
        type: 'scatter',
        data: (chart.points ?? []).map((point) => [point.x, point.y, point.label ?? '']),
        symbolSize: 11,
      },
    ],
  }
}

/** points를 category별 scatter series로 나누고 size 값으로 버블 크기를 계산합니다. */
function buildBubbleOption(chart: AnalyticsChartPayload): EChartsOption {
  const points = chart.points ?? []
  const maxSize = Math.max(...points.map((point) => normalizeBubbleSizeValue(point.size)), 1)
  const groupedPoints = groupBubblePoints(points)
  const axisLayout = resolveValueAxisLayout(chart)

  return {
    ...buildBaseOption(axisLayout),
    legend: {
      type: 'scroll',
      top: 0,
      right: 0,
      textStyle: { color: '#475569' },
    },
    tooltip: {
      trigger: 'item',
      confine: true,
      backgroundColor: 'rgba(15, 23, 42, 0.92)',
      borderWidth: 0,
      textStyle: { color: '#fff' },
      formatter(params: TooltipParam | TooltipParam[]) {
        if (Array.isArray(params)) return ''
        const data = Array.isArray(params.data) ? params.data : []
        const label = data[3] ? `${data[3]}<br/>` : ''
        const size = data[2] ?? '-'
        return `${label}${chart.meta?.x_label ?? 'x'}: ${data[0]}<br/>${chart.meta?.y_label ?? 'y'}: ${data[1]}<br/>규모: ${size}`
      },
    },
    xAxis: buildValueXAxis(chart, axisLayout),
    yAxis: buildValueYAxis(chart, axisLayout),
    series: Object.entries(groupedPoints).map(([category, categoryPoints]) => ({
      name: category,
      type: 'scatter',
      data: categoryPoints.map((point) => [
        point.x,
        point.y,
        normalizeBubbleSizeValue(point.size),
        point.label ?? category,
      ]),
      symbolSize(data: unknown) {
        const size = Array.isArray(data) ? normalizeBubbleSizeValue(data[2]) : 0
        return 14 + Math.sqrt(size / maxSize) * 34
      },
    })),
  }
}

/** value 축 차트에서 축 제목 유무에 맞춰 여백을 계산합니다. */
function resolveValueAxisLayout(chart: AnalyticsChartPayload): ValueAxisLayout {
  const hasXAxisName = Boolean(chart.meta?.x_label)
  const hasYAxisName = Boolean(chart.meta?.y_label)

  return {
    // 값 축 차트는 축 제목을 플롯에서 조금 떼고, 카드 바깥 여백은 과하게 쓰지 않도록 균형을 맞춥니다.
    bottom: hasXAxisName ? 60 : 44,
    left: hasYAxisName ? 30 : 40,
    xNameGap: hasXAxisName ? 50 : 32,
    yNameGap: hasYAxisName ? 92 : 56,
  }
}

/** value 기반 x축 설정을 공통화합니다. */
function buildValueXAxis(chart: AnalyticsChartPayload, axisLayout: ValueAxisLayout) {
  return {
    type: 'value',
    name: chart.meta?.x_label ?? undefined,
    nameGap: axisLayout.xNameGap,
    nameLocation: 'middle',
    nameTextStyle: { color: '#475569', fontWeight: 700 },
    splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.2)' } },
    axisLabel: { color: '#64748b' },
  }
}

/** value 기반 y축 설정을 공통화합니다. */
function buildValueYAxis(chart: AnalyticsChartPayload, axisLayout: ValueAxisLayout) {
  return {
    type: 'value',
    name: chart.meta?.y_label ?? undefined,
    nameGap: axisLayout.yNameGap,
    nameLocation: 'middle',
    nameRotate: 90,
    nameTextStyle: { color: '#475569', fontWeight: 700 },
    splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.2)' } },
    axisLabel: { color: '#64748b', margin: 10 },
  }
}

/** x label과 첫 번째 series 값을 도넛 segment로 매핑합니다. */
function buildDonutOption(chart: AnalyticsChartPayload): EChartsOption {
  const values = chart.series[0]?.data ?? []
  return {
    ...buildBaseOption(),
    tooltip: {
      trigger: 'item',
      confine: true,
      backgroundColor: 'rgba(15, 23, 42, 0.92)',
      borderWidth: 0,
      textStyle: { color: '#fff' },
    },
    legend: {
      orient: 'vertical',
      right: 0,
      top: 'middle',
      textStyle: { color: '#475569' },
    },
    series: [
      {
        name: chart.title,
        type: 'pie',
        radius: ['52%', '76%'],
        center: ['38%', '50%'],
        avoidLabelOverlap: true,
        label: { formatter: '{b}', color: '#475569' },
        data: values.map((value, index) => ({
          name: chart.x[index] ?? `항목 ${index + 1}`,
          value: normalizeNumericValue(value),
        })),
      },
    ],
  }
}

/** 차트 payload가 없을 때 기존 대시보드 포인트를 혼합형 차트로 표시합니다. */
function buildFallbackOption(points: ChartPoint[]): EChartsOption {
  return buildBarLineOption({
    type: 'metric',
    title: 'Fallback',
    x: points.map((point) => point.label),
    series: [{ name: 'value', data: points.map((point) => point.spend) }],
  })
}

/** 축 차트 값은 숫자 문자열이면 숫자로 바꾸고, 그 외 문자열은 그대로 둡니다. */
function normalizeAxisValue(value: number | string | null): number | string | null {
  if (value === null) return null
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : value
}

/** pie처럼 숫자만 받는 차트 값은 변환 실패 시 0으로 보정합니다. */
function normalizeNumericValue(value: number | string | null): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

/** 버블 크기는 음수와 비정상 값을 0으로 고정합니다. */
function normalizeBubbleSizeValue(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? Math.max(value, 0) : 0
}

/** 버블 범례와 series를 만들기 위해 points를 category 단위로 묶습니다. */
function groupBubblePoints(points: NonNullable<AnalyticsChartPayload['points']>) {
  return points.reduce<Record<string, NonNullable<AnalyticsChartPayload['points']>>>((groups, point) => {
    const category = point.category || point.label || '세그먼트'
    groups[category] = [...(groups[category] ?? []), point]
    return groups
  }, {})
}
