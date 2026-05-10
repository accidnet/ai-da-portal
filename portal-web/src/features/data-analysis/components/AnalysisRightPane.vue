<script setup lang="ts">
import AnalysisVisualizationPane from './AnalysisVisualizationPane.vue'
import type {
  AnalyticsData,
  AnalyticsPayload,
  WorkspacePayload,
} from '../types'

defineProps<{
  shellAnalytics: AnalyticsData
  analyticsPayload: AnalyticsPayload | null
  workspacePayload: WorkspacePayload | null
  isCompactLayout: boolean
  isAnalyticsPanelOpen: boolean
  isAnalyticsFullscreen: boolean
  isLoading: boolean
  analyticsError: string | null
  canExportReport: boolean
}>()

const emit = defineEmits<{
  toggleFullscreen: []
  exportReport: []
  shareReport: []
  closeAnalyticsPanel: []
}>()
</script>

<template>
  <div
    class="analysis-right-pane"
    :class="{
      'analysis-right-pane--compact': isCompactLayout,
      'analysis-right-pane--open': isAnalyticsPanelOpen,
    }"
  >
    <div v-if="isCompactLayout" class="analysis-right-pane__header">
      <strong>시각화 패널</strong>
      <button type="button" class="analysis-right-pane__close" @click="emit('closeAnalyticsPanel')">
        <span class="material-symbols-outlined">close</span>
      </button>
    </div>

    <AnalysisVisualizationPane
      :analytics="shellAnalytics"
      :analytics-payload="analyticsPayload"
      :workspace-payload="workspacePayload"
      :is-loading="isLoading"
      :error-message="analyticsError"
      :is-fullscreen="isAnalyticsFullscreen"
      :export-disabled="!canExportReport"
      :share-disabled="!canExportReport"
      @toggle-fullscreen="emit('toggleFullscreen')"
      @export-report="emit('exportReport')"
      @share-report="emit('shareReport')"
    />
  </div>

  <div
    v-if="isCompactLayout && isAnalyticsPanelOpen"
    class="analysis-right-pane-backdrop"
    @click="emit('closeAnalyticsPanel')"
  ></div>
</template>

<style scoped>
.analysis-right-pane {
  min-width: 0;
  min-height: 0;
  height: 100%;
}

.analysis-right-pane__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding: 0 4px;
}

.analysis-right-pane__header strong {
  color: var(--color-primary-strong);
  font-size: 0.95rem;
}

.analysis-right-pane__close {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.92);
  color: var(--color-primary-strong);
  cursor: pointer;
}

.analysis-right-pane-backdrop {
  position: fixed;
  inset: 0;
  z-index: 11;
  background: rgba(15, 23, 42, 0.28);
}

@media (max-width: 960px) {
  .analysis-right-pane--compact {
    position: fixed;
    top: 16px;
    right: 16px;
    bottom: 16px;
    z-index: 12;
    width: min(420px, calc(100vw - 32px));
    padding: 14px;
    border-radius: 24px;
    background: rgba(245, 247, 251, 0.96);
    box-shadow: 0 24px 56px rgba(15, 23, 42, 0.18);
    transform: translateX(calc(100% + 24px));
    transition: transform 220ms ease;
  }

  .analysis-right-pane--open {
    transform: translateX(0);
  }
}
</style>
