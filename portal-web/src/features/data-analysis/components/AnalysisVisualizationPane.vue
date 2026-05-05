<script setup lang="ts">
import { computed } from 'vue'

import { resolveVisualizationComponent } from './visualizations'

import type {
  AnalyticsChartPayload,
  AnalyticsData,
  AnalyticsPayload,
  WorkspacePayload,
  WorkspaceSectionPayload,
} from '@/features/data-analysis/types'

type ChartWorkspaceSection = WorkspaceSectionPayload & { kind: 'chart' }

const props = defineProps<{
  analytics: AnalyticsData
  analyticsPayload?: AnalyticsPayload | null
  workspacePayload?: WorkspacePayload | null
  isLoading?: boolean
  errorMessage?: string | null
  isFullscreen?: boolean
  exportDisabled?: boolean
  shareDisabled?: boolean
}>()

const emit = defineEmits<{
  toggleFullscreen: []
  exportReport: []
  shareReport: []
}>()

const backendCharts = computed(() => props.analyticsPayload?.charts ?? [])
const chartSections = computed<ChartWorkspaceSection[]>(() => {
  const workspaceChartSections = props.workspacePayload?.sections.filter(
    (section): section is ChartWorkspaceSection => section.kind === 'chart',
  ) ?? []
  if (workspaceChartSections.length) return workspaceChartSections

  return backendCharts.value.map((_, index) => ({
    kind: 'chart',
    title: index === 0 ? '주요 차트' : `차트 ${index + 1}`,
    chart_index: index,
  }))
})
const hasChartData = computed(() => chartSections.value.some((section) => Boolean(chartForSection(section))))
const shareTooltip = '공유 링크 복사'
const exportTooltip = '리포트 미리보기'
const fullscreenTooltip = computed(() => (props.isFullscreen ? '전체 화면 종료' : '전체 화면 보기'))

function chartForSection(section: ChartWorkspaceSection): AnalyticsChartPayload | null {
  return backendCharts.value[section.chart_index ?? 0] ?? null
}

function visualizationComponent(section: ChartWorkspaceSection) {
  return resolveVisualizationComponent(chartForSection(section))
}
</script>

<template>
  <aside class="analytics-shell" :class="props.workspacePayload ? `analytics-shell--${props.workspacePayload.template_id}` : null">
    <header class="analytics-header">
      <div>
        <h2>시각화</h2>
      </div>

      <div class="analytics-actions">
        <button
          type="button"
          :aria-label="shareTooltip"
          :title="shareTooltip"
          :data-tooltip="shareTooltip"
          :disabled="props.shareDisabled"
          @click="emit('shareReport')"
        >
          <span class="material-symbols-outlined">link</span>
        </button>
        <button
          type="button"
          :aria-label="exportTooltip"
          :title="exportTooltip"
          :data-tooltip="exportTooltip"
          :disabled="props.exportDisabled"
          @click="emit('exportReport')"
        >
          <span class="material-symbols-outlined">preview</span>
        </button>
        <button
          type="button"
          :aria-label="fullscreenTooltip"
          :title="fullscreenTooltip"
          :data-tooltip="fullscreenTooltip"
          @click="emit('toggleFullscreen')"
        >
          <span class="material-symbols-outlined">{{ props.isFullscreen ? 'fullscreen_exit' : 'fullscreen' }}</span>
        </button>
      </div>
    </header>

    <p v-if="errorMessage" class="analytics-alert">{{ errorMessage }}</p>
    <p v-else-if="isLoading" class="analytics-alert analytics-alert--loading">실시간 분석 결과를 업데이트하고 있어요...</p>

    <template v-for="(section, sectionIndex) in chartSections" :key="`chart-${sectionIndex}`">
      <section v-if="chartForSection(section)" class="panel-card chart-card">
        <div class="chart-headline">
          <div>
            <h3>{{ chartForSection(section)?.title }}</h3>
          </div>
        </div>

        <component
          :is="visualizationComponent(section)"
          :chart="chartForSection(section)"
          :fallback-points="props.analytics.chartPoints"
        />
      </section>
    </template>

    <section v-if="!hasChartData && !isLoading && !errorMessage" class="analytics-empty-state">
      <span class="material-symbols-outlined">analytics</span>
      <strong>아직 표시할 분석 데이터가 없어요</strong>
      <p>CSV를 업로드하거나 분석을 실행하면 이 영역에 차트가 나타납니다.</p>
    </section>
  </aside>
</template>

<style scoped>
.analytics-shell {
  min-height: 0;
  display: grid;
  gap: 18px;
  align-content: start;
  overflow-y: auto;
  padding: 22px 18px 22px 22px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: rgba(244, 247, 251, 0.78);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
}

.analytics-header,
.chart-headline {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.analytics-header p,
.chart-headline p {
  margin: 0;
  color: var(--color-text-soft);
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.68rem;
  font-weight: 800;
}

.analytics-header h2,
.chart-headline h3 {
  margin: 6px 0 0;
  color: var(--color-text);
  font-family: var(--font-heading);
}

.analytics-header h2 {
  font-size: 1.05rem;
}

.analytics-actions {
  display: flex;
  gap: 8px;
}

.analytics-actions button {
  position: relative;
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
  background: var(--color-surface-muted);
  cursor: pointer;
}

.analytics-actions button:hover:not(:disabled),
.analytics-actions button:focus-visible {
  border-color: rgba(24, 74, 140, 0.16);
  color: var(--color-primary-strong);
  outline: none;
}

.analytics-actions button:hover:not(:disabled)::after,
.analytics-actions button:focus-visible::after {
  content: attr(data-tooltip);
  position: absolute;
  right: 0;
  bottom: calc(100% + 8px);
  padding: 6px 8px;
  border-radius: 10px;
  white-space: nowrap;
  color: #fff;
  font-size: 0.72rem;
  line-height: 1.2;
  background: rgba(15, 23, 42, 0.9);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.18);
  pointer-events: none;
}

.analytics-actions button:disabled {
  opacity: 0.45;
  cursor: default;
}

.analytics-alert {
  margin: 0;
  padding: 12px 16px;
  border-radius: 16px;
  color: #825b17;
  background: rgba(226, 189, 106, 0.14);
  border: 1px solid rgba(226, 189, 106, 0.18);
}

.analytics-alert--loading {
  color: #1f5ca8;
  background: rgba(31, 92, 168, 0.12);
  border-color: rgba(31, 92, 168, 0.16);
}

.analytics-empty-state {
  display: grid;
  place-items: center;
  gap: 10px;
  min-height: 220px;
  padding: 28px;
  border: 1px dashed rgba(24, 74, 140, 0.18);
  border-radius: 24px;
  color: var(--color-text-muted);
  text-align: center;
  background: rgba(255, 255, 255, 0.56);
}

.analytics-empty-state .material-symbols-outlined {
  font-size: 2rem;
  color: var(--color-primary);
}

.analytics-empty-state strong,
.analytics-empty-state p {
  margin: 0;
}

.analytics-empty-state strong {
  color: var(--color-text);
}

.panel-card {
  border: 1px solid var(--color-border);
  border-radius: 24px;
  background: var(--color-surface);
  box-shadow: var(--color-shadow);
}

.chart-card {
  padding: 20px;
}

@media (max-width: 1280px) {
  .analytics-shell {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .analytics-header,
  .chart-card {
    grid-column: 1 / -1;
  }
}

@media (max-width: 720px) {
  .analytics-shell {
    grid-template-columns: minmax(0, 1fr);
  }

  .analytics-shell {
    padding: 18px;
  }

  .analytics-header,
  .chart-headline {
    display: grid;
  }
}
</style>
