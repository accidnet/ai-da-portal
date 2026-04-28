<script setup lang="ts">
import { computed } from 'vue'

import type { AnalyticsChartPayload, ChartPoint } from '../../types'
import { resolveChartBadge, resolveSeriesPoints } from './chartUtils'

const props = defineProps<{
  chart: AnalyticsChartPayload | null
  fallbackPoints: ChartPoint[]
  fallbackBadge: string
}>()

const points = computed(() => resolveSeriesPoints(props.chart, props.fallbackPoints))
const hasData = computed(() => points.value.some((point) => point.value > 0))
const badge = computed(() => resolveChartBadge(props.chart, props.fallbackBadge))
</script>

<template>
  <div class="viz-shell">
    <div class="viz-header"><span>{{ badge }}</span></div>
    <div v-if="hasData" class="viz-bars">
      <div v-for="point in points" :key="point.label" class="viz-bar-item">
        <div class="viz-bar-track">
          <div class="viz-bar-fill" :style="{ height: `${Math.min(point.value, 100)}%` }"></div>
        </div>
        <small>{{ point.label }}</small>
      </div>
    </div>
    <p v-else class="viz-empty">표시할 막대 차트 데이터가 없어요.</p>
  </div>
</template>

<style scoped>
.viz-shell { display:grid; gap:16px; }
.viz-header { display:flex; justify-content:flex-end; }
.viz-header span { padding:8px 10px; border-radius:999px; color:var(--color-primary-strong); background:var(--color-surface-muted); font-weight:700; font-size:0.8rem; }
.viz-bars { min-height:220px; display:grid; grid-template-columns:repeat(auto-fit, minmax(36px, 1fr)); gap:10px; align-items:end; padding:12px 0 8px; }
.viz-bar-item { height:220px; display:grid; gap:8px; align-items:end; justify-items:center; }
.viz-bar-track { width:100%; height:190px; display:flex; align-items:flex-end; }
.viz-bar-fill { width:100%; min-height:12px; border-radius:14px 14px 6px 6px; background:linear-gradient(180deg, rgba(24, 74, 140, 0.5), rgba(24, 74, 140, 0.2)); }
.viz-bar-item small { color:var(--color-text-soft); font-size:0.68rem; text-align:center; }
.viz-empty { margin:0; min-height:220px; display:grid; place-items:center; color:var(--color-text-soft); }
</style>
