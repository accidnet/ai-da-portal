import type { Component } from 'vue'

import type { AnalyticsChartPayload } from '../../types'

import AreaTrend from './AreaTrend.vue'
import BarChart from './BarChart.vue'
import BarLine from './BarLine.vue'
import DonutShare from './DonutShare.vue'
import LineTrend from './LineTrend.vue'
import ScatterPlot from './ScatterPlot.vue'

export { AreaTrend, BarChart, BarLine, DonutShare, LineTrend, ScatterPlot }

const visualizationById: Record<string, Component> = {
  trend_line: LineTrend,
  category_bar: BarChart,
  category_area: AreaTrend,
  correlation_scatter: ScatterPlot,
  share_donut: DonutShare,
}

const visualizationByType: Record<string, Component> = {
  line: LineTrend,
  bar: BarChart,
  area: AreaTrend,
  scatter: ScatterPlot,
  donut: DonutShare,
}

// id가 우선이고, 없으면 type 기준으로 시각화를 선택합니다.
export function resolveVisualizationComponent(chart: AnalyticsChartPayload | null): Component {
  if (!chart) return BarLine
  return visualizationById[chart.id ?? ''] ?? visualizationByType[chart.type] ?? BarLine
}
