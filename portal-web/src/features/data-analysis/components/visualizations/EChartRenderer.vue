<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { BarChart, LineChart, PieChart, ScatterChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { init, use, type ECharts, type EChartsCoreOption as EChartsOption } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

import type { AnalyticsChartPayload, AnalyticsChartType, ChartPoint } from '@/features/data-analysis/types'

type RendererType = AnalyticsChartType | 'bar_line'
type TooltipParam = { data?: unknown }

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
  if (resolvedType === 'scatter') return buildScatterOption(chart)
  if (resolvedType === 'donut') return buildDonutOption(chart)
  if (resolvedType === 'area') return buildAxisOption(chart, 'line', true)
  if (resolvedType === 'line') return buildAxisOption(chart, 'line', false)
  if (resolvedType === 'bar') return buildAxisOption(chart, 'bar', false)
  return buildBarLineOption(chart)
}

function buildBaseOption(): EChartsOption {
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
      bottom: 34,
      left: 44,
      containLabel: true,
    },
  }
}

function buildAxisOption(chart: AnalyticsChartPayload, type: 'line' | 'bar', isArea: boolean): EChartsOption {
  return {
    ...buildBaseOption(),
    xAxis: {
      type: 'category',
      data: chart.x,
      name: chart.meta?.x_label ?? undefined,
      boundaryGap: type === 'bar',
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#cbd5e1' } },
      axisLabel: { color: '#64748b' },
    },
    yAxis: {
      type: 'value',
      name: chart.meta?.y_label ?? undefined,
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.2)' } },
      axisLabel: { color: '#64748b' },
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
    ...buildBaseOption(),
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
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.2)' } },
      axisLabel: { color: '#64748b' },
    },
    yAxis: {
      type: 'value',
      name: chart.meta?.y_label ?? undefined,
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.2)' } },
      axisLabel: { color: '#64748b' },
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
  height: 260px;
  min-height: 260px;
}
</style>
