<script setup lang="ts">
import EChartRenderer from './EChartRenderer.vue'

import type { AnalyticsChartPayload, ChartPoint } from '@/features/data-analysis/types'

defineProps<{
  chart: AnalyticsChartPayload | null
  fallbackPoints: ChartPoint[]
}>()
</script>

<template>
  <EChartRenderer
    chart-type="bar_line"
    :chart="chart"
    :fallback-points="fallbackPoints"
  />
</template>
