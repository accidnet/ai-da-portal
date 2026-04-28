<script setup lang="ts">
import { computed } from 'vue'

import type { AnalyticsChartPayload, ChartPoint } from '../../types'
import { resolveChartBadge, resolveScatterBounds } from './chartUtils'

const props = defineProps<{
  chart: AnalyticsChartPayload | null
  fallbackPoints: ChartPoint[]
  fallbackBadge: string
}>()

const scatterPoints = computed(() => props.chart?.points ?? [])
const hasData = computed(() => scatterPoints.value.length > 0)
const bounds = computed(() => resolveScatterBounds(props.chart))
const badge = computed(() => resolveChartBadge(props.chart, props.fallbackBadge))

function pointX(value: number) {
  return ((value - bounds.value.minX) / bounds.value.spanX) * 100
}

function pointY(value: number) {
  return 100 - ((value - bounds.value.minY) / bounds.value.spanY) * 100
}
</script>

<template>
  <div class="viz-shell">
    <div class="viz-header"><span>{{ badge }}</span></div>
    <div class="viz-body">
      <svg v-if="hasData" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <path class="viz-axis" d="M 10 90 L 95 90 M 10 10 L 10 90"></path>
        <circle
          v-for="(point, index) in scatterPoints"
          :key="point.label ?? index"
          class="viz-dot"
          :cx="10 + pointX(point.x) * 0.85"
          :cy="10 + pointY(point.y) * 0.8"
          r="2.2"
        />
      </svg>
      <div v-if="hasData" class="viz-meta">
        <small>{{ props.chart?.meta?.x_label ?? 'x' }}</small>
        <small>{{ props.chart?.meta?.y_label ?? 'y' }}</small>
      </div>
      <p v-else class="viz-empty">표시할 산점도 데이터가 없어요.</p>
    </div>
  </div>
</template>

<style scoped>
.viz-shell { display:grid; gap:16px; }
.viz-header { display:flex; justify-content:flex-end; }
.viz-header span { padding:8px 10px; border-radius:999px; color:var(--color-primary-strong); background:var(--color-surface-muted); font-weight:700; font-size:0.8rem; }
.viz-body { min-height:220px; display:grid; gap:10px; }
.viz-body svg { width:100%; height:220px; background:linear-gradient(180deg, rgba(244, 247, 251, 0.8), rgba(255, 255, 255, 0.92)); border-radius:18px; }
.viz-axis { fill:none; stroke:rgba(15, 23, 42, 0.24); stroke-width:1.2; }
.viz-dot { fill:rgba(24, 74, 140, 0.75); }
.viz-meta { display:flex; justify-content:space-between; gap:12px; }
.viz-meta small { color:var(--color-text-soft); font-size:0.74rem; }
.viz-empty { margin:0; min-height:220px; display:grid; place-items:center; color:var(--color-text-soft); }
</style>
