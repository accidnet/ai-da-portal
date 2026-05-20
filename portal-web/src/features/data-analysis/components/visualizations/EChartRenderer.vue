<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { BarChart, LineChart, PieChart, ScatterChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { init, use, type ECharts, type EChartsCoreOption as EChartsOption } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

import type { AnalyticsChartPayload, AnalyticsChartType, ChartPoint } from '@/features/data-analysis/types'

type RendererType = AnalyticsChartType | 'bar_line'
type TooltipParam = { data?: unknown }
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

use([BarChart, LineChart, PieChart, ScatterChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{
  chart: AnalyticsChartPayload | null
  chartType?: RendererType
  fallbackPoints: ChartPoint[]
}>()

const chartElement = ref<HTMLDivElement | null>(null)
const chartInstance = shallowRef<ECharts | null>(null)
let resizeObserver: ResizeObserver | null = null

const option = computed(() => buildChartOption(props.chart, props.chartType, props.fallbackPoints))

onMounted(() => {
  if (!chartElement.value) return
  chartInstance.value = init(chartElement.value, undefined, { renderer: 'canvas' })
  resizeObserver = new ResizeObserver(() => chartInstance.value?.resize())
  resizeObserver.observe(chartElement.value)
  renderChart()
})

watch(option, renderChart, { deep: true })

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  chartInstance.value?.dispose()
  chartInstance.value = null
})

function renderChart() {
  if (!chartInstance.value) return
  chartInstance.value.setOption(option.value, true)
}

function hasRenderableData(chart: AnalyticsChartPayload | null): boolean {
  if (!chart) return false
  if (chart.points?.length) return true
  return chart.series.some((series) => series.data.length > 0)
}

function buildChartOption(
  chart: AnalyticsChartPayload | null,
  chartType: RendererType | undefined,
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
  if (resolvedType === 'line') return buildAxisOption(chart, 'line', false)
  if (resolvedType === 'bar') return buildAxisOption(chart, 'bar', false)
  return buildBarLineOption(chart)
}

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

function buildScatterOption(chart: AnalyticsChartPayload): EChartsOption {
  return {
    ...buildBaseOption({
      bottom: chart.meta?.x_label ? 72 : 48,
      left: chart.meta?.y_label ? 92 : 44,
    }),
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
    xAxis: {
      type: 'value',
      name: chart.meta?.x_label ?? undefined,
      nameGap: 42,
      nameLocation: 'middle',
      nameTextStyle: { color: '#475569', fontWeight: 700 },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.2)' } },
      axisLabel: { color: '#64748b' },
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

function buildBubbleOption(chart: AnalyticsChartPayload): EChartsOption {
  const points = chart.points ?? []
  const maxSize = Math.max(...points.map((point) => normalizeBubbleSizeValue(point.size)), 1)
  const groupedPoints = groupBubblePoints(points)

  return {
    ...buildBaseOption({
      bottom: chart.meta?.x_label ? 72 : 48,
      left: chart.meta?.y_label ? 92 : 44,
    }),
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
    xAxis: {
      type: 'value',
      name: chart.meta?.x_label ?? undefined,
      nameGap: 42,
      nameLocation: 'middle',
      nameTextStyle: { color: '#475569', fontWeight: 700 },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.2)' } },
      axisLabel: { color: '#64748b' },
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

function buildFallbackOption(points: ChartPoint[]): EChartsOption {
  return buildBarLineOption({
    type: 'metric',
    title: 'Fallback',
    x: points.map((point) => point.label),
    series: [{ name: 'value', data: points.map((point) => point.spend) }],
  })
}

function normalizeAxisValue(value: number | string | null): number | string | null {
  if (value === null) return null
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : value
}

function normalizeNumericValue(value: number | string | null): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function normalizeBubbleSizeValue(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? Math.max(value, 0) : 0
}

function groupBubblePoints(points: NonNullable<AnalyticsChartPayload['points']>) {
  return points.reduce<Record<string, NonNullable<AnalyticsChartPayload['points']>>>((groups, point) => {
    const category = point.category || point.label || '세그먼트'
    groups[category] = [...(groups[category] ?? []), point]
    return groups
  }, {})
}
</script>

<template>
  <div class="echart-shell">
    <div ref="chartElement" class="echart-canvas" role="img" :aria-label="chart?.title ?? '차트'"></div>
  </div>
</template>

<style scoped>
.echart-shell {
  display: grid;
}

.echart-canvas {
  width: 100%;
  height: 300px;
  min-height: 300px;
}
</style>
