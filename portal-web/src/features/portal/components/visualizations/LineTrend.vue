<script setup lang="ts">
import { computed } from 'vue'

import type { AnalyticsChartPayload, ChartPoint } from '../../types'
import { resolveChartBadge, resolveLinePath, resolveSeriesPoints } from './chartUtils'

const props = defineProps<{
  chart: AnalyticsChartPayload | null
  fallbackPoints: ChartPoint[]
  fallbackBadge: string
}>()

const points = computed(() => resolveSeriesPoints(props.chart, props.fallbackPoints))
const hasData = computed(() => points.value.some((point) => point.value > 0))
const linePath = computed(() => resolveLinePath(points.value))
const badge = computed(() => resolveChartBadge(props.chart, props.fallbackBadge))
</script>

<template>
  <div class="viz-shell">
    <div class="viz-header"><span>{{ badge }}</span></div>
    <div class="viz-body">
      <svg v-if="hasData" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <path class="viz-grid" d="M 0 85 L 100 85 M 0 55 L 100 55 M 0 25 L 100 25"></path>
        <path class="viz-line" :d="linePath"></path>
      </svg>
      <div v-if="hasData" class="viz-labels">
        <small v-for="point in points" :key="point.label">{{ point.label }}</small>
      </div>
      <p v-else class="viz-empty">표시할 라인 차트 데이터가 없어요.</p>
    </div>
  </div>
</template>

<style scoped>
.viz-shell { display:grid; gap:16px; }
.viz-header { display:flex; justify-content:flex-end; }
.viz-header span { padding:8px 10px; border-radius:999px; color:var(--color-primary-strong); background:var(--color-surface-muted); font-weight:700; font-size:0.8rem; }
.viz-body { min-height:220px; display:grid; gap:10px; }
.viz-body svg { width:100%; height:200px; }
.viz-grid { fill:none; stroke:rgba(24, 74, 140, 0.12); stroke-width:1; }
.viz-line { fill:none; stroke:var(--color-primary); stroke-width:2.5; stroke-linecap:round; stroke-linejoin:round; }
.viz-labels { display:grid; grid-template-columns:repeat(auto-fit, minmax(32px, 1fr)); gap:8px; }
.viz-labels small { color:var(--color-text-soft); font-size:0.68rem; text-align:center; }
.viz-empty { margin:0; min-height:220px; display:grid; place-items:center; color:var(--color-text-soft); }
</style>
