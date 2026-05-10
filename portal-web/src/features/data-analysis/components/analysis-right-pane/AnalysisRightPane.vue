<script setup lang="ts">
import { ref } from 'vue'

import AnalysisConnectedDataPane from './AnalysisConnectedDataPane.vue'
import AnalysisVisualizationPane from './AnalysisVisualizationPane.vue'
import type {
  AnalyticsData,
  AnalyticsPayload,
  DatasetAsset,
  WorkspacePayload,
} from '@/features/data-analysis/types'

type PaneMode = 'visualization' | 'data'

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
  connectedDatasets: DatasetAsset[]
  isDatasetMutating: boolean
}>()

const emit = defineEmits<{
  toggleFullscreen: []
  exportReport: []
  shareReport: []
  closeAnalyticsPanel: []
  uploadDataset: []
  selectDataset: [datasetId: string]
  detachDataset: [datasetId: string]
}>()

const activeMode = ref<PaneMode>('data')

/** 우측 패널에서 표시할 분석 보조 화면을 전환합니다. */
function setMode(mode: PaneMode) {
  activeMode.value = mode
}
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
      <strong>{{ activeMode === 'data' ? '연결 데이터' : '시각화 패널' }}</strong>
      <button type="button" class="analysis-right-pane__close" @click="emit('closeAnalyticsPanel')">
        <span class="material-symbols-outlined">close</span>
      </button>
    </div>

    <div class="analysis-right-pane__toolbar">
      <div class="pane-switch" aria-label="분석 우측 패널 모드">
        <button
          type="button"
          class="pane-switch__button"
          :class="{ 'pane-switch__button--active': activeMode === 'visualization' }"
          @click="setMode('visualization')"
        >
          시각화
        </button>
        <button
          type="button"
          class="pane-switch__button"
          :class="{ 'pane-switch__button--active': activeMode === 'data' }"
          @click="setMode('data')"
        >
          연결 데이터
        </button>
      </div>
    </div>

    <AnalysisVisualizationPane
      v-if="activeMode === 'visualization'"
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

    <AnalysisConnectedDataPane
      v-else
      :connected-datasets="connectedDatasets"
      :is-dataset-mutating="isDatasetMutating"
      @upload-dataset="emit('uploadDataset')"
      @select-dataset="(datasetId) => emit('selectDataset', datasetId)"
      @detach-dataset="(datasetId) => emit('detachDataset', datasetId)"
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
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 32px;
  overflow: hidden;
  padding: 35px 30px 28px;
  border-radius: 24px;
  background: #fff;
  box-shadow: 0 18px 60px rgba(37, 68, 112, 0.08);
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

.analysis-right-pane__toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 16px;
}

.pane-switch {
  display: flex;
  height: 40px;
  padding: 3px;
  border-radius: 10px;
  background: #eef3f9;
}

.pane-switch__button {
  height: 34px;
  padding: 0 14px;
  border: 0;
  border-radius: 8px;
  color: var(--color-primary);
  background: transparent;
  font: inherit;
  font-size: 15px;
  font-weight: 800;
  cursor: pointer;
  transition: background-color 150ms ease, color 150ms ease, box-shadow 150ms ease, transform 150ms ease;
}

.pane-switch__button:hover {
  background: rgba(255, 255, 255, 0.65);
  transform: translateY(-1px);
}

.pane-switch__button--active,
.pane-switch__button--active:hover {
  color: #fff;
  background: var(--color-primary);
  box-shadow: 0 4px 10px rgba(43, 94, 162, 0.24);
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
