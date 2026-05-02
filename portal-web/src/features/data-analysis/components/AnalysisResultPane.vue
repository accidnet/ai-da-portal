<script setup lang="ts">
import { computed } from 'vue'

import { resolveVisualizationComponent } from './visualizations'

import type {
  AnalyticsChartPayload,
  AnalyticsData,
  AnalyticsPayload,
  AnalyticsSummaryCard,
  AnalyticsTablePayload,
  DatasetAsset,
  WorkspacePayload,
  WorkspaceSectionPayload,
} from '../types'

const props = defineProps<{
  analytics: AnalyticsData
  analyticsPayload?: AnalyticsPayload | null
  workspacePayload?: WorkspacePayload | null
  datasetAsset?: DatasetAsset | null
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

const backendSummaryCards = computed(() => props.analyticsPayload?.summary_cards ?? [])
const backendCharts = computed(() => props.analyticsPayload?.charts ?? [])
const backendTables = computed(() => props.analyticsPayload?.tables ?? [])
const backendDatasetProfile = computed(
  () => props.datasetAsset?.profile ?? normalizeDatasetProfile(props.analyticsPayload?.dataset_profile),
)

const fallbackWorkspace = computed<WorkspacePayload | null>(() => {
  if (!props.analyticsPayload) return null

  return {
    template_id: 'overview',
    title: props.analytics.title,
    description: '기본 analytics payload 기반 작업공간',
    sections: [
      { kind: 'summary_cards', title: '핵심 지표', max_items: 4 },
      { kind: 'chart', title: '주요 차트', chart_index: 0 },
      { kind: 'table', title: '상세 표', table_index: 0 },
      { kind: 'dataset_profile', title: '데이터 스냅샷' },
    ],
  }
})

const workspacePayload = computed(() => props.workspacePayload ?? fallbackWorkspace.value)
const workspaceSections = computed(() => workspacePayload.value?.sections.filter((section) => section.kind !== 'insight') ?? [])
const hasWorkspaceData = computed(() => workspaceSections.value.some(hasSectionContent))
const workspaceTitle = computed(() => workspacePayload.value?.title ?? props.analytics.title)
const shareTooltip = '공유 링크 복사'
const exportTooltip = '리포트 미리보기'
const fullscreenTooltip = computed(() => (props.isFullscreen ? '전체 화면 종료' : '전체 화면 보기'))

function normalizeDatasetProfile(payload: AnalyticsPayload['dataset_profile'] | undefined | null): DatasetAsset['profile'] | null {
  if (!payload) return null

  return {
    rowCount: payload.row_count,
    columnCount: payload.column_count,
    columns: payload.columns.map((column) => ({
      name: column.name,
      dtype: column.dtype,
      nullRatio: column.null_ratio,
      sampleValues: column.sample_values,
    })),
  }
}

function hasSectionContent(section: WorkspaceSectionPayload): boolean {
  if (section.kind === 'summary_cards') return summaryCardsForSection(section).length > 0
  if (section.kind === 'chart') return Boolean(chartForSection(section))
  if (section.kind === 'table') return Boolean(tableForSection(section))
  return Boolean(backendDatasetProfile.value)
}

function summaryCardsForSection(section: WorkspaceSectionPayload): AnalyticsSummaryCard[] {
  const cards = backendSummaryCards.value
  const labels = section.summary_card_labels?.filter(Boolean) ?? []
  const filtered = labels.length ? cards.filter((card) => labels.includes(card.label)) : cards
  return filtered.slice(0, section.max_items ?? filtered.length)
}

function chartForSection(section: WorkspaceSectionPayload): AnalyticsChartPayload | null {
  return backendCharts.value[section.chart_index ?? 0] ?? null
}

function tableForSection(section: WorkspaceSectionPayload): AnalyticsTablePayload | null {
  return backendTables.value[section.table_index ?? 0] ?? null
}

function visualizationComponent(section: WorkspaceSectionPayload) {
  return resolveVisualizationComponent(chartForSection(section))
}
</script>

<template>
  <aside class="analytics-shell" :class="workspacePayload ? `analytics-shell--${workspacePayload.template_id}` : null">
    <header class="analytics-header">
      <div>
        <p>시각화</p>
        <h2>{{ workspaceTitle }}</h2>
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

    <template v-for="(section, sectionIndex) in workspaceSections" :key="`${section.kind}-${sectionIndex}`">
      <section v-if="section.kind === 'chart' && chartForSection(section)" class="panel-card chart-card">
        <div class="chart-headline">
          <div>
            <p>{{ section.title ?? '차트' }}</p>
            <h3>{{ chartForSection(section)?.title }}</h3>
          </div>
        </div>

        <component
          :is="visualizationComponent(section)"
          :chart="chartForSection(section)"
          :fallback-points="props.analytics.chartPoints"
          :fallback-badge="props.analytics.chartChange"
        />
      </section>

      <section v-else-if="section.kind === 'summary_cards' && summaryCardsForSection(section).length" class="workspace-section">
        <header v-if="section.title" class="workspace-section__header">
          <p>{{ section.title }}</p>
        </header>
        <div class="metric-grid">
          <article v-for="card in summaryCardsForSection(section)" :key="card.label" class="panel-card metric-card">
            <p>{{ card.label }}</p>
            <strong :class="`metric-value--${card.tone ?? 'primary'}`">{{ card.value }}</strong>
            <span>{{ card.detail }}</span>
            <div class="meter-track">
              <div class="meter-fill" :class="`meter-fill--${card.tone ?? 'primary'}`"></div>
            </div>
          </article>
        </div>
      </section>

      <section v-else-if="section.kind === 'table' && tableForSection(section)" class="panel-card table-card">
        <header>
          <p>{{ section.title ?? '분석 결과' }}</p>
          <h3>{{ tableForSection(section)?.title }}</h3>
        </header>

        <table>
          <thead>
            <tr>
              <th v-for="column in tableForSection(section)?.columns ?? []" :key="column.key">{{ column.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, rowIndex) in tableForSection(section)?.rows ?? []" :key="rowIndex">
              <td v-for="column in tableForSection(section)?.columns ?? []" :key="column.key">{{ row[column.key] }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section v-else-if="section.kind === 'dataset_profile' && backendDatasetProfile" class="panel-card dataset-card">
        <header class="dataset-card__header">
          <div>
            <p>{{ section.title ?? '데이터 스냅샷' }}</p>
            <h3>{{ datasetAsset?.filename ?? '선택된 데이터셋이 없어요' }}</h3>
          </div>
          <span v-if="backendDatasetProfile">{{ backendDatasetProfile.rowCount }}행</span>
        </header>

        <div v-if="backendDatasetProfile" class="dataset-stats">
          <article class="dataset-stat">
            <p>행 수</p>
            <strong>{{ backendDatasetProfile.rowCount }}</strong>
          </article>
          <article class="dataset-stat">
            <p>열 수</p>
            <strong>{{ backendDatasetProfile.columnCount }}</strong>
          </article>
        </div>

        <div v-if="backendDatasetProfile" class="dataset-columns">
          <article v-for="column in backendDatasetProfile.columns" :key="column.name" class="dataset-column">
            <strong>{{ column.name }}</strong>
            <span>{{ column.dtype }} · 결측 {{ Math.round(column.nullRatio * 100) }}%</span>
            <small v-if="column.sampleValues.length">예시값: {{ column.sampleValues.join(', ') }}</small>
          </article>
        </div>
      </section>
    </template>

    <section v-if="!hasWorkspaceData && !isLoading && !errorMessage" class="analytics-empty-state">
      <span class="material-symbols-outlined">analytics</span>
      <strong>아직 표시할 분석 데이터가 없어요</strong>
      <p>CSV를 업로드하거나 분석을 실행하면 이 영역에 차트와 카드가 나타납니다.</p>
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
.chart-headline,
.dataset-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.analytics-header p,
.chart-headline p,
.metric-card p,
.table-card p,
.dataset-card p,
.dataset-column span,
.dataset-stat p,
.prompt-list p,
.workspace-section__header p {
  margin: 0;
  color: var(--color-text-soft);
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.68rem;
  font-weight: 800;
}

.analytics-header h2,
.chart-headline h3,
.table-card h3,
.dataset-card h3 {
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

.chart-card,
.table-card,
.dataset-card,
.metric-card {
  padding: 20px;
}

.dataset-card__header span {
  padding: 8px 10px;
  border-radius: 999px;
  color: var(--color-primary-strong);
  background: var(--color-surface-muted);
  font-weight: 700;
  font-size: 0.8rem;
}

.workspace-section {
  display: grid;
  gap: 12px;
}

.metric-grid,
.dataset-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.metric-card strong,
.dataset-stat strong {
  display: block;
  margin-top: 12px;
  font: 800 1.5rem/1 var(--font-heading);
}

.metric-value--primary {
  color: var(--color-primary);
}

.metric-value--warning {
  color: var(--color-warning);
}

.metric-card span {
  display: block;
  margin-top: 10px;
  color: var(--color-text-muted);
  font-size: 0.8rem;
}

.meter-track {
  margin-top: 14px;
  height: 8px;
  border-radius: 999px;
  background: rgba(24, 74, 140, 0.1);
  overflow: hidden;
}

.meter-fill {
  height: 100%;
  border-radius: inherit;
}

.meter-fill--primary {
  width: 98%;
  background: var(--color-primary);
}

.meter-fill--warning {
  width: 38%;
  background: #a25918;
}

.table-card table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 16px;
}

.table-card th,
.table-card td {
  padding: 14px 0;
  border-bottom: 1px solid var(--color-border);
}

.table-card th {
  color: var(--color-text-soft);
  font-size: 0.7rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  text-align: left;
}

.table-card td:nth-child(2),
.table-card td:nth-child(3),
.table-card th:nth-child(2),
.table-card th:nth-child(3) {
  text-align: right;
}

.dataset-stats {
  margin-top: 16px;
  gap: 12px;
}

.dataset-stat,
.dataset-column {
  padding: 14px;
  border-radius: 18px;
  background: var(--color-surface-muted);
}

.dataset-columns {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.dataset-column strong {
  display: block;
  font-size: 0.88rem;
}

.dataset-column span,
.dataset-column small {
  display: block;
  margin-top: 6px;
}

.dataset-column small {
  color: var(--color-text-muted);
  line-height: 1.5;
}

.prompt-list {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.prompt-list button {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--color-border);
  text-align: left;
  color: var(--color-text);
  background: var(--color-surface-muted);
  cursor: pointer;
}

.prompt-list button:disabled {
  opacity: 0.65;
  cursor: default;
}

@media (max-width: 1280px) {
  .analytics-shell {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .analytics-header,
  .chart-card,
  .dataset-card {
    grid-column: 1 / -1;
  }
}

@media (max-width: 720px) {
  .analytics-shell,
  .metric-grid,
  .dataset-stats {
    grid-template-columns: minmax(0, 1fr);
  }

  .analytics-shell {
    padding: 18px;
  }

  .analytics-header,
  .chart-headline,
  .dataset-card__header {
    display: grid;
  }
}
</style>
