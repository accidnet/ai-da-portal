import { defineAsyncComponent, type Component } from 'vue'

import type { AnalyticsChartPayload } from '@/features/data-analysis/types'

// 차트 렌더러와 echarts 의존성은 시각화가 필요할 때 별도 chunk로 로드합니다.
const AreaTrend = defineAsyncComponent(() => import('./AreaTrend.vue'))
const BarChart = defineAsyncComponent(() => import('./BarChart.vue'))
const BarLine = defineAsyncComponent(() => import('./BarLine.vue'))
const DonutShare = defineAsyncComponent(() => import('./DonutShare.vue'))
const LineTrend = defineAsyncComponent(() => import('./LineTrend.vue'))
const ScatterPlot = defineAsyncComponent(() => import('./ScatterPlot.vue'))

export { AreaTrend, BarChart, BarLine, DonutShare, LineTrend, ScatterPlot }

const visualizationById: Record<string, Component> = {
  trend_line: LineTrend,
  category_bar: BarChart,
  category_area: AreaTrend,
  correlation_scatter: ScatterPlot,
  segment_bubble: ScatterPlot,
  share_donut: DonutShare,
}

const visualizationByType: Record<string, Component> = {
  line: LineTrend,
  bar: BarChart,
  area: AreaTrend,
  scatter: ScatterPlot,
  bubble: ScatterPlot,
  donut: DonutShare,
}

// id가 우선이고, 없으면 type 기준으로 시각화를 선택합니다.
export function resolveVisualizationComponent(chart: AnalyticsChartPayload | null): Component {
  if (!chart) return BarLine
  return visualizationById[chart.id ?? ''] ?? visualizationByType[chart.type] ?? BarLine
}
