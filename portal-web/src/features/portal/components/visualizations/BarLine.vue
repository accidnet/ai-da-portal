<script setup lang="ts">
import { computed } from 'vue'

import type { AnalyticsChartPayload, ChartPoint } from '../../types'

const props = defineProps<{
  chart: AnalyticsChartPayload | null
  fallbackPoints: ChartPoint[]
  fallbackBadge: string
}>()

// 백엔드 값이 비어 있어도 기본 시각화가 유지되도록 정규화합니다.
function normalizePoint(value: number | string | null | undefined): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

const points = computed(() => {
  if (props.chart && props.chart.x.length > 0 && props.chart.series.length > 0) {
    const series = props.chart.series[0]
    return props.chart.x.map((label, index) => ({
      label,
      value: normalizePoint(series.data[index]),
    }))
  }

  return props.fallbackPoints.map((point) => ({
    label: point.label,
    value: point.spend,
  }))
})

const hasData = computed(() => points.value.some((point) => point.value > 0))

const linePath = computed(() => {
  if (points.value.length === 0) return ''

  const maxValue = Math.max(...points.value.map((point) => point.value), 1)
  if (points.value.length === 1) return 'M 0 50 L 100 50'

  return points.value
    .map((point, index) => {
      const x = (index / (points.value.length - 1)) * 100
      const y = 100 - (point.value / maxValue) * 100
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`
    })
    .join(' ')
})

const badge = computed(() => (props.chart?.series[0]?.data.length ? '실시간 백엔드 결과' : props.fallbackBadge))
</script>

<template>
  <div class="visualization-shell">
    <div class="visualization-header">
      <span>{{ badge }}</span>
    </div>

    <div class="visualization-body">
      <div v-if="hasData" class="visualization-bars">
        <div v-for="point in points" :key="point.label" class="visualization-bar-item">
          <div class="visualization-bar-fill" :style="{ height: `${Math.min(point.value, 100)}%` }"></div>
          <small>{{ point.label }}</small>
        </div>
      </div>

      <svg v-if="hasData" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <path :d="linePath"></path>
      </svg>

      <p v-else class="visualization-empty">아직 차트 데이터가 없어요. 프롬프트를 보내거나 분석을 실행해 주세요.</p>
    </div>
  </div>
</template>

<style scoped>
.visualization-shell {
  display: grid;
  gap: 16px;
}

.visualization-header {
  display: flex;
  justify-content: flex-end;
}

.visualization-header span {
  padding: 8px 10px;
  border-radius: 999px;
  color: var(--color-primary-strong);
  background: var(--color-surface-muted);
  font-weight: 700;
  font-size: 0.8rem;
}

.visualization-body {
  position: relative;
  height: 220px;
  padding: 12px 0 24px;
}

.visualization-empty {
  margin: 0;
  height: 100%;
  display: grid;
  place-items: center;
  color: var(--color-text-soft);
  font-size: 0.9rem;
  text-align: center;
}

.visualization-bars {
  position: absolute;
  inset: 12px 0 24px;
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 8px;
  align-items: end;
}

.visualization-bar-item {
  height: 100%;
  display: grid;
  align-items: end;
  justify-items: center;
  gap: 8px;
}

.visualization-bar-fill {
  width: 100%;
  min-height: 12px;
  border-radius: 999px 999px 8px 8px;
  background: rgba(24, 74, 140, 0.24);
}

.visualization-bar-item small {
  color: var(--color-text-soft);
  font-size: 0.68rem;
}

.visualization-body svg {
  position: absolute;
  inset: 0 0 24px;
  width: 100%;
  height: calc(100% - 24px);
}

.visualization-body path {
  fill: none;
  stroke: var(--color-primary);
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}
</style>
