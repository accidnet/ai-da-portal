<script setup lang="ts">
import { computed } from 'vue'

import type { AnalyticsChartPayload, ChartPoint } from '../../types'
import { resolveChartBadge, resolveDonutSegments } from './chartUtils'

const props = defineProps<{
  chart: AnalyticsChartPayload | null
  fallbackPoints: ChartPoint[]
  fallbackBadge: string
}>()

const segments = computed(() => resolveDonutSegments(props.chart))
const hasData = computed(() => segments.value.some((segment) => segment.value > 0))
const badge = computed(() => resolveChartBadge(props.chart, props.fallbackBadge))
const colors = ['#184a8c', '#3c78c9', '#6f9edb', '#9fbee8', '#c5d8f1', '#dce8f8']

const donutBackground = computed(() => {
  if (!hasData.value) return 'conic-gradient(#e5edf6 0deg 360deg)'

  let currentAngle = 0
  const stops = segments.value.map((segment, index) => {
    const start = currentAngle
    const end = currentAngle + segment.ratio * 360
    currentAngle = end
    return `${colors[index % colors.length]} ${start}deg ${end}deg`
  })
  return `conic-gradient(${stops.join(', ')})`
})
</script>

<template>
  <div class="viz-shell">
    <div class="viz-header"><span>{{ badge }}</span></div>
    <div v-if="hasData" class="viz-body">
      <div class="viz-donut" :style="{ background: donutBackground }">
        <div class="viz-donut-core"></div>
      </div>
      <div class="viz-legend">
        <div v-for="(segment, index) in segments" :key="segment.label" class="viz-legend-item">
          <span class="viz-swatch" :style="{ backgroundColor: colors[index % colors.length] }"></span>
          <strong>{{ segment.label }}</strong>
          <small>{{ Math.round(segment.ratio * 100) }}%</small>
        </div>
      </div>
    </div>
    <p v-else class="viz-empty">표시할 도넛 차트 데이터가 없어요.</p>
  </div>
</template>

<style scoped>
.viz-shell { display:grid; gap:16px; }
.viz-header { display:flex; justify-content:flex-end; }
.viz-header span { padding:8px 10px; border-radius:999px; color:var(--color-primary-strong); background:var(--color-surface-muted); font-weight:700; font-size:0.8rem; }
.viz-body { display:grid; grid-template-columns:minmax(180px, 220px) minmax(0, 1fr); gap:20px; align-items:center; }
.viz-donut { width:220px; aspect-ratio:1; border-radius:50%; display:grid; place-items:center; }
.viz-donut-core { width:96px; aspect-ratio:1; border-radius:50%; background:var(--color-surface); box-shadow:inset 0 0 0 1px var(--color-border); }
.viz-legend { display:grid; gap:10px; }
.viz-legend-item { display:grid; grid-template-columns:auto 1fr auto; align-items:center; gap:10px; padding:10px 12px; border-radius:14px; background:var(--color-surface-muted); }
.viz-swatch { width:10px; height:10px; border-radius:999px; }
.viz-legend-item strong { font-size:0.84rem; color:var(--color-text); }
.viz-legend-item small { color:var(--color-text-soft); }
.viz-empty { margin:0; min-height:220px; display:grid; place-items:center; color:var(--color-text-soft); }
@media (max-width: 720px) { .viz-body { grid-template-columns:minmax(0, 1fr); justify-items:center; } }
</style>
