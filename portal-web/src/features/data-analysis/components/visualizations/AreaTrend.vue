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
    chart-type="area"
    :chart="chart"
    :fallback-points="fallbackPoints"
  />
</template>
