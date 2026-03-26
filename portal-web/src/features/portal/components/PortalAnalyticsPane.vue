<script setup lang="ts">
import { computed } from 'vue'

import type { AnalyticsData } from '../types'

const props = defineProps<{
  analytics: AnalyticsData
}>()

const chartPath = computed(() => {
  const points = props.analytics.chartPoints
  const maxValue = Math.max(...points.map((point) => point.spend))

  return points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * 100
      const y = 100 - (point.spend / maxValue) * 100
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`
    })
    .join(' ')
})
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

    <section class="panel-card chart-card">
      <div class="chart-headline">
        <div>
          <p>Growth Trend</p>
          <h3>{{ analytics.chartTitle }}</h3>
        </div>
        <span>{{ analytics.chartChange }}</span>
      </div>

      <div class="chart-body">
        <div class="chart-bars">
          <div v-for="point in analytics.chartPoints" :key="point.label" class="bar-item">
            <div class="bar-fill" :style="{ height: `${point.spend}%` }"></div>
            <small>{{ point.label }}</small>
          </div>
        </div>

        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <path :d="chartPath"></path>
        </svg>
      </div>
    </section>

    <section class="metric-grid">
      <article v-for="metric in analytics.metrics" :key="metric.label" class="panel-card metric-card">
        <p>{{ metric.label }}</p>
        <strong :class="`metric-value--${metric.tone ?? 'primary'}`">{{ metric.value }}</strong>
        <span>{{ metric.meta }}</span>
        <div class="meter-track">
          <div class="meter-fill" :class="`meter-fill--${metric.tone ?? 'primary'}`"></div>
        </div>
      </article>
    </section>

    <section class="panel-card table-card">
      <header>
        <p>Performance</p>
        <h3>Key Metric Breakdown</h3>
      </header>

      <table>
        <thead>
          <tr>
            <th>Channel</th>
            <th>ROI</th>
            <th>Trend</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in analytics.tableRows" :key="row.channel">
            <td>{{ row.channel }}</td>
            <td>{{ row.roi }}</td>
            <td>
              <span :class="['trend-pill', `trend-pill--${row.trend}`]">
                <span class="material-symbols-outlined">
                  {{ row.trend === 'up' ? 'trending_up' : 'trending_flat' }}
                </span>
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="insight-card">
      <div class="insight-icon">
        <span class="material-symbols-outlined">lightbulb</span>
      </div>
      <div>
        <p>{{ analytics.insight.title }}</p>
        <h3>{{ analytics.insight.body }}</h3>
        <button type="button">{{ analytics.insight.actionLabel }}</button>
      </div>
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
  padding-right: 4px;
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
.insight-card p {
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
.insight-card h3 {
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
  color: var(--color-text-muted);
  background: rgba(255, 255, 255, 0.7);
  cursor: pointer;
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

.table-card table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 16px;
}

.table-card th,
.table-card td {
  padding: 14px 0;
  border-bottom: 1px solid var(--color-border);
  font-size: 0.86rem;
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
  .insight-card {
    grid-column: 1 / -1;
  }
}

@media (max-width: 720px) {
  .analytics-shell,
  .metric-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .insight-card {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
