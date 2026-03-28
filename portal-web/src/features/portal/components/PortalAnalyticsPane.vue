<script setup lang="ts">
import { computed } from 'vue'

import type {
  AnalyticsData,
  AnalyticsPayload,
  DatasetAsset,
  DatasetPreview,
} from '../types'

const props = defineProps<{
  analytics: AnalyticsData
  analyticsPayload?: AnalyticsPayload | null
  datasetAsset?: DatasetAsset | null
  isLoading?: boolean
  errorMessage?: string | null
}>()

const emit = defineEmits<{
  promptClick: [prompt: string]
  insightAction: []
}>()

const backendChart = computed(() => props.analyticsPayload?.charts[0] ?? null)
const backendSummaryCards = computed(() => props.analyticsPayload?.summary_cards ?? [])
const backendTables = computed(() => props.analyticsPayload?.tables ?? [])
const backendInsights = computed(() => props.analyticsPayload?.insights ?? [])
const backendDatasetProfile = computed(
  () => props.datasetAsset?.profile ?? normalizeDatasetProfile(props.analyticsPayload?.dataset_profile),
)
const backendDatasetPreview = computed(() => props.datasetAsset?.preview ?? null)

const displayChartPoints = computed(() => {
  const chart = backendChart.value
  if (chart && chart.x.length > 0 && chart.series.length > 0) {
    const series = chart.series[0]
    return chart.x.map((label, index) => ({
      label,
      value: normalizePoint(series.data[index]),
    }))
  }

  return props.analytics.chartPoints.map((point) => ({
    label: point.label,
    value: point.spend,
  }))
})

const hasChartData = computed(() => displayChartPoints.value.some((point) => point.value > 0))
const chartPath = computed(() => {
  const points = displayChartPoints.value

  if (points.length === 0) {
    return ''
  }

  const maxValue = Math.max(...points.map((point) => point.value), 1)

  if (points.length === 1) {
    return 'M 0 50 L 100 50'
  }

  return points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * 100
      const y = 100 - (point.value / maxValue) * 100
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`
    })
    .join(' ')
})
const hasBackendTable = computed(() => backendTables.value.length > 0)
const backendTable = computed(() => backendTables.value[0] ?? null)
const displayInsight = computed(() => backendInsights.value[0] ?? null)
const hasDatasetPreview = computed(() => (backendDatasetPreview.value?.rows?.length ?? 0) > 0)
const hasWorkspaceData = computed(() => (
  Boolean(backendChart.value)
  || backendSummaryCards.value.length > 0
  || hasBackendTable.value
  || Boolean(backendDatasetProfile.value)
  || hasDatasetPreview.value
  || Boolean(displayInsight.value)
))
const chartTitle = computed(() => backendChart.value?.title ?? props.analytics.chartTitle)
const chartChange = computed(() => {
  if (backendChart.value?.series[0]?.data.length) {
    return 'Live backend payload'
  }

  return props.analytics.chartChange
})

function normalizePoint(value: number | string | null | undefined): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }

  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function normalizeDatasetProfile(
  payload:
    | AnalyticsPayload['dataset_profile']
    | undefined
    | null,
): DatasetAsset['profile'] | null {
  if (!payload) {
    return null
  }

  return {
    rowCount: payload.row_count,
    columnCount: payload.column_count,
    columns: payload.columns.map((column) => ({
      name: column.name,
      dtype: column.dtype,
      nullRatio: column.null_ratio,
      sampleValues: column.sample_values,
    })),
    suggestedPrompts: payload.suggested_prompts,
  }
}

function previewRows(preview: DatasetPreview | null): Array<Record<string, string | number | null>> {
  return preview?.rows ?? []
}
</script>

<template>
  <aside class="analytics-shell">
    <header class="analytics-header">
      <div>
        <p>Workspace</p>
        <h2>{{ analytics.title }}</h2>
      </div>

      <div class="analytics-actions">
        <button type="button" aria-label="Fullscreen view">
          <span class="material-symbols-outlined">fullscreen</span>
        </button>
        <button type="button" aria-label="Download report">
          <span class="material-symbols-outlined">download</span>
        </button>
      </div>
    </header>

    <p v-if="errorMessage" class="analytics-alert">{{ errorMessage }}</p>
    <p v-else-if="isLoading" class="analytics-alert analytics-alert--loading">Updating live analytics...</p>

    <section v-if="backendChart" class="panel-card chart-card">
      <div class="chart-headline">
        <div>
          <p>Growth Trend</p>
          <h3>{{ chartTitle }}</h3>
        </div>
        <span>{{ chartChange }}</span>
      </div>

      <div class="chart-body">
        <div v-if="hasChartData" class="chart-bars">
          <div v-for="point in displayChartPoints" :key="point.label" class="bar-item">
            <div class="bar-fill" :style="{ height: `${Math.min(point.value, 100)}%` }"></div>
            <small>{{ point.label }}</small>
          </div>
        </div>

        <svg v-if="hasChartData" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <path :d="chartPath"></path>
        </svg>

        <p v-else class="chart-empty">No chart data available yet. Send a prompt or run an analysis.</p>
      </div>
    </section>

    <section v-if="backendSummaryCards.length" class="metric-grid">
      <article
        v-for="card in backendSummaryCards"
        :key="card.label"
        class="panel-card metric-card"
      >
        <p>{{ card.label }}</p>
        <strong :class="`metric-value--${card.tone ?? 'primary'}`">{{ card.value }}</strong>
        <span>{{ card.detail }}</span>
        <div class="meter-track">
          <div class="meter-fill" :class="`meter-fill--${card.tone ?? 'primary'}`"></div>
        </div>
      </article>
    </section>

    <section v-if="hasBackendTable" class="panel-card table-card">
      <header>
        <p>Performance</p>
        <h3>{{ backendTable?.title }}</h3>
      </header>

      <table>
        <thead>
          <tr>
            <template v-if="backendTable">
              <th v-for="column in backendTable.columns" :key="column.key">{{ column.label }}</th>
            </template>
          </tr>
        </thead>
        <tbody>
          <template v-if="backendTable">
            <tr v-for="(row, rowIndex) in backendTable.rows" :key="rowIndex">
              <td v-for="column in backendTable.columns" :key="column.key">
                {{ row[column.key] }}
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </section>

    <section v-if="backendDatasetProfile || hasDatasetPreview" class="panel-card dataset-card">
      <header class="dataset-card__header">
        <div>
          <p>Data Snapshot</p>
          <h3>{{ datasetAsset?.filename ?? 'No dataset selected' }}</h3>
        </div>
        <span v-if="backendDatasetProfile">
          {{ backendDatasetProfile.rowCount }} rows
        </span>
      </header>

      <div v-if="backendDatasetProfile" class="dataset-stats">
        <article class="dataset-stat">
          <p>Rows</p>
          <strong>{{ backendDatasetProfile.rowCount }}</strong>
        </article>
        <article class="dataset-stat">
          <p>Columns</p>
          <strong>{{ backendDatasetProfile.columnCount }}</strong>
        </article>
      </div>

      <div v-if="backendDatasetProfile" class="dataset-columns">
        <article v-for="column in backendDatasetProfile.columns" :key="column.name" class="dataset-column">
          <strong>{{ column.name }}</strong>
          <span>{{ column.dtype }} · null {{ Math.round(column.nullRatio * 100) }}%</span>
          <small v-if="column.sampleValues.length">Samples: {{ column.sampleValues.join(', ') }}</small>
        </article>
      </div>

      <div v-if="hasDatasetPreview && backendDatasetPreview" class="dataset-preview">
        <table>
          <thead>
            <tr>
              <th v-for="column in backendDatasetPreview.columns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, rowIndex) in previewRows(backendDatasetPreview)" :key="rowIndex">
              <td v-for="column in backendDatasetPreview.columns" :key="column">
                {{ row[column] }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="backendDatasetProfile?.suggestedPrompts.length" class="prompt-list">
        <p>Suggested prompts</p>
        <button
          v-for="prompt in backendDatasetProfile.suggestedPrompts"
          :key="prompt"
          type="button"
          :disabled="isLoading"
          @click="emit('promptClick', prompt)"
        >
          {{ prompt }}
        </button>
      </div>
    </section>

    <section v-if="displayInsight" class="insight-card">
      <div class="insight-icon">
        <span class="material-symbols-outlined">lightbulb</span>
      </div>
      <div>
        <p>{{ displayInsight.title }}</p>
        <h3>{{ displayInsight.body }}</h3>
        <button type="button" :disabled="isLoading" @click="emit('insightAction')">
          {{ displayInsight.action_label ?? analytics.insight.actionLabel }}
        </button>
      </div>
    </section>

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

.analytics-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 6px 4px;
}

.analytics-header p,
.chart-headline p,
.metric-card p,
.table-card p,
.insight-card p,
.dataset-card p,
.dataset-column span,
.dataset-stat p,
.prompt-list p {
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
.insight-card h3,
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
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  border: 0;
  color: var(--color-text-muted);
  background: rgba(255, 255, 255, 0.7);
  cursor: pointer;
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

.panel-card,
.insight-card {
  border: 1px solid var(--color-border);
  border-radius: 24px;
  background: var(--color-surface);
  box-shadow: var(--color-shadow);
}

.chart-card,
.table-card,
.dataset-card,
.insight-card {
  padding: 20px;
}

.chart-headline {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.chart-headline span {
  padding: 8px 10px;
  border-radius: 999px;
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  font-weight: 700;
  font-size: 0.8rem;
}

.chart-body {
  position: relative;
  height: 220px;
  margin-top: 16px;
  padding: 12px 0 24px;
}

.chart-empty {
  margin: 0;
  height: 100%;
  display: grid;
  place-items: center;
  color: var(--color-text-soft);
  font-size: 0.9rem;
  text-align: center;
}

.chart-bars {
  position: absolute;
  inset: 12px 0 24px;
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 8px;
  align-items: end;
}

.bar-item {
  height: 100%;
  display: grid;
  align-items: end;
  justify-items: center;
  gap: 8px;
}

.bar-fill {
  width: 100%;
  min-height: 12px;
  border-radius: 999px 999px 8px 8px;
  background: linear-gradient(180deg, rgba(24, 74, 140, 0.12) 0%, rgba(24, 74, 140, 0.28) 100%);
}

.bar-item small {
  color: var(--color-text-soft);
  font-size: 0.68rem;
}

.chart-body svg {
  position: absolute;
  inset: 0 0 24px;
  width: 100%;
  height: calc(100% - 24px);
}

.chart-body path {
  fill: none;
  stroke: var(--color-primary);
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.metric-card {
  padding: 18px;
}

.metric-card strong {
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
  background: linear-gradient(90deg, var(--color-primary) 0%, #4b88d7 100%);
}

.meter-fill--warning {
  width: 38%;
  background: linear-gradient(90deg, #dd9c5b 0%, #a25918 100%);
}

.table-card table,
.dataset-preview table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 16px;
}

.table-card th,
.table-card td,
.dataset-preview th,
.dataset-preview td {
  padding: 14px 0;
  border-bottom: 1px solid var(--color-border);
  font-size: 0.86rem;
}

.table-card th,
.dataset-preview th {
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

.trend-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.trend-pill--up {
  color: var(--color-success);
}

.trend-pill--flat {
  color: var(--color-text-soft);
}

.dataset-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.dataset-card__header span {
  padding: 8px 10px;
  border-radius: 999px;
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  font-weight: 700;
  font-size: 0.8rem;
}

.dataset-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.dataset-stat,
.dataset-column {
  padding: 14px;
  border-radius: 18px;
  background: var(--color-surface-muted);
}

.dataset-stat strong {
  display: block;
  margin-top: 6px;
  font: 800 1.5rem/1 var(--font-heading);
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

.dataset-column span {
  display: block;
  margin-top: 6px;
}

.dataset-column small {
  display: block;
  margin-top: 8px;
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
  border: 0;
  text-align: left;
  color: var(--color-text);
  background: var(--color-surface-muted);
  cursor: pointer;
}

.prompt-list button:disabled,
.insight-card button:disabled {
  opacity: 0.65;
  cursor: default;
}

.insight-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 14px;
  align-items: start;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92) 0%, rgba(228, 238, 249, 0.92) 100%);
}

.insight-icon {
  width: 42px;
  height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  color: var(--color-primary);
  background: rgba(24, 74, 140, 0.1);
}

.insight-card button {
  margin-top: 18px;
  width: 100%;
  padding: 14px 16px;
  border-radius: 16px;
  border: 0;
  color: #fff;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-strong) 100%);
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  cursor: pointer;
}

@media (max-width: 1280px) {
  .analytics-shell {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .analytics-header,
  .chart-card,
  .insight-card,
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

  .insight-card {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
