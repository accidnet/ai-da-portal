<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { BarChart, LineChart, PieChart, ScatterChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { init, use, type ECharts } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

import { buildChartOption, type ChartRendererType } from './chartOptions'

import type { AnalyticsChartPayload, ChartPoint } from '@/features/data-analysis/types'

use([BarChart, LineChart, PieChart, ScatterChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{
  chart: AnalyticsChartPayload | null
  chartType?: ChartRendererType
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
