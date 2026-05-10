<script setup lang="ts">
import { computed, ref } from 'vue'

import AnalysisVisualizationPane from './AnalysisVisualizationPane.vue'
import type {
  AnalyticsData,
  AnalyticsPayload,
  DatasetAsset,
  WorkspacePayload,
} from '../types'

type PaneMode = 'visualization' | 'data'

const props = defineProps<{
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
const expandedDatasetId = ref<string | null>(null)
const hiddenDatasetIds = ref<Set<string>>(new Set())
const hiddenColumnKeys = ref<Set<string>>(new Set())

const selectedDeleteLabel = computed(() => `선택한 데이터 모두 삭제 (0/${props.connectedDatasets.length})`)

function setMode(mode: PaneMode) {
  activeMode.value = mode
}

/** 연결 데이터의 파일 트리를 열거나 닫습니다. */
function toggleDatasetOpen(datasetId: string) {
  expandedDatasetId.value = expandedDatasetId.value === datasetId ? null : datasetId
  emit('selectDataset', datasetId)
}

/** 데이터 카드의 표시/숨김 상태를 로컬 UI 상태로 전환합니다. */
function toggleDatasetVisibility(datasetId: string) {
  const next = new Set(hiddenDatasetIds.value)
  if (next.has(datasetId)) {
    next.delete(datasetId)
  } else {
    next.add(datasetId)
  }
  hiddenDatasetIds.value = next
}

/** 컬럼 행의 표시/숨김 상태를 로컬 UI 상태로 전환합니다. */
function toggleColumnVisibility(datasetId: string, columnName: string) {
  const key = `${datasetId}:${columnName}`
  const next = new Set(hiddenColumnKeys.value)
  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  hiddenColumnKeys.value = next
}

function isDatasetVisible(datasetId: string): boolean {
  return !hiddenDatasetIds.value.has(datasetId)
}

function isColumnVisible(datasetId: string, columnName: string): boolean {
  return !hiddenColumnKeys.value.has(`${datasetId}:${columnName}`)
}

function formatDatasetMeta(dataset: DatasetAsset): string {
  const rowCount = dataset.profile?.rowCount ?? dataset.preview?.rows.length ?? 0
  const columnCount = dataset.profile?.columnCount ?? dataset.preview?.columns.length ?? 0
  return `${rowCount.toLocaleString()}행 · ${columnCount.toLocaleString()}열`
}

function fileRows(dataset: DatasetAsset): Array<{ name: string; depth: number }> {
  const columns = dataset.profile?.columns.map((column) => column.name) ?? dataset.preview?.columns ?? []
  return columns.slice(0, 6).map((name, index) => ({
    name,
    depth: index === 0 ? 1 : 2,
  }))
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

      <button type="button" class="pane-add-button" aria-label="데이터 추가" @click="emit('uploadDataset')">
        <span class="material-symbols-outlined">add</span>
      </button>
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

    <section v-else class="connected-data-pane">
      <h2>세션과 연결된 데이터</h2>

      <label class="bulk-delete-row">
        <span class="checkbox" aria-hidden="true"></span>
        <span>{{ selectedDeleteLabel }}</span>
      </label>

      <div class="connected-data-pane__divider"></div>

      <div v-if="connectedDatasets.length" class="dataset-card-list">
        <article
          v-for="dataset in connectedDatasets"
          :key="dataset.id"
          class="dataset-card"
          :class="{
            'dataset-card--open': expandedDatasetId === dataset.id,
            'dataset-card--hidden': !isDatasetVisible(dataset.id),
          }"
        >
          <div class="dataset-card__body">
            <div class="dataset-card__top">
              <label class="select-label">
                <span class="checkbox" aria-hidden="true"></span>
                <span>선택</span>
              </label>

              <div class="dataset-card__actions">
                <button type="button" class="soft-button" :disabled="isDatasetMutating" @click="emit('selectDataset', dataset.id)">
                  변경
                </button>
                <button
                  v-if="expandedDatasetId !== dataset.id"
                  type="button"
                  class="gray-button"
                  :disabled="isDatasetMutating"
                  @click="toggleDatasetOpen(dataset.id)"
                >
                  열기
                </button>
                <button type="button" class="primary-button" :disabled="isDatasetMutating" @click="emit('detachDataset', dataset.id)">
                  삭제
                </button>
              </div>
            </div>

            <div class="dataset-card__divider"></div>

            <div class="dataset-card__name-row">
              <div class="dataset-card__title">
                <strong>{{ dataset.filename }}</strong>
                <span>{{ formatDatasetMeta(dataset) }}</span>
              </div>
              <button
                type="button"
                class="visibility-button"
                :aria-label="isDatasetVisible(dataset.id) ? '데이터 보이기' : '데이터 숨김'"
                @click="toggleDatasetVisibility(dataset.id)"
              >
                <span class="material-symbols-outlined">{{ isDatasetVisible(dataset.id) ? 'visibility' : 'visibility_off' }}</span>
              </button>
            </div>
          </div>

          <div v-if="expandedDatasetId === dataset.id" class="file-tree">
            <div class="file-tree__rows">
              <div class="file-row file-row--root">
                <span class="material-symbols-outlined file-row__icon">description</span>
                <span class="file-row__name">{{ dataset.filename }}</span>
                <button type="button" class="visibility-button" @click="toggleDatasetVisibility(dataset.id)">
                  <span class="material-symbols-outlined">{{ isDatasetVisible(dataset.id) ? 'visibility' : 'visibility_off' }}</span>
                </button>
              </div>

              <div
                v-for="row in fileRows(dataset)"
                :key="`${dataset.id}-${row.name}`"
                class="file-row"
                :class="{ 'file-row--hidden': !isColumnVisible(dataset.id, row.name) }"
                :style="{ '--file-depth': row.depth }"
              >
                <span class="file-row__branch">ㄴ</span>
                <span class="material-symbols-outlined file-row__icon">description</span>
                <span class="file-row__name">{{ row.name }}</span>
                <button type="button" class="visibility-button" @click="toggleColumnVisibility(dataset.id, row.name)">
                  <span class="material-symbols-outlined">{{ isColumnVisible(dataset.id, row.name) ? 'visibility' : 'visibility_off' }}</span>
                </button>
              </div>
            </div>

            <button type="button" class="tree-close-button" @click="expandedDatasetId = null">닫기</button>
            <div class="file-tree__fade"></div>
          </div>
        </article>
      </div>

      <section v-else class="empty-data-state">
        <span class="material-symbols-outlined">database</span>
        <strong>연결된 데이터가 없습니다</strong>
        <p>상단의 추가 버튼으로 파일을 업로드하면 현재 세션에 바로 연결됩니다.</p>
      </section>
    </section>
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

.analysis-right-pane__toolbar,
.dataset-card__top,
.dataset-card__actions,
.dataset-card__name-row,
.bulk-delete-row,
.select-label {
  display: flex;
  align-items: center;
}

.analysis-right-pane__toolbar {
  justify-content: space-between;
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

.pane-add-button {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid var(--color-primary);
  border-radius: 6px;
  color: var(--color-primary);
  background: #fff;
  cursor: pointer;
  transition: background-color 150ms ease, color 150ms ease, box-shadow 150ms ease, transform 150ms ease;
}

.pane-add-button:hover,
.pane-add-button:focus-visible {
  color: #fff;
  background: var(--color-primary);
  box-shadow: 0 4px 12px rgba(43, 94, 162, 0.24);
  outline: none;
  transform: translateY(-1px);
}

.connected-data-pane {
  min-height: 0;
  display: grid;
  grid-template-rows: auto auto auto minmax(0, 1fr);
  overflow: hidden;
}

.connected-data-pane h2 {
  margin: 37px 0 0;
  color: #000;
  font-size: 18px;
  font-weight: 800;
}

.bulk-delete-row {
  gap: 8px;
  margin-top: 27px;
  color: #000;
  font-size: 14px;
}

.checkbox {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  border: 1px solid #000;
  background: #fff;
}

.connected-data-pane__divider {
  width: 100%;
  height: 1px;
  margin-top: 12px;
  background: #d9d9d9;
}

.dataset-card-list {
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 16px;
  margin-top: 24px;
  overflow-y: auto;
  padding-right: 4px;
}

.dataset-card {
  overflow: hidden;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.dataset-card--open {
  background: #ededed;
}

.dataset-card--hidden .dataset-card__title {
  opacity: 0.2;
}

.dataset-card__body {
  padding: 16px;
  background: #fff;
}

.dataset-card__top {
  justify-content: space-between;
  gap: 12px;
}

.select-label {
  gap: 6px;
  color: #000;
  font-size: 14px;
}

.dataset-card__actions {
  justify-content: flex-end;
  gap: 4px;
}

.soft-button,
.gray-button,
.primary-button {
  min-height: 25px;
  padding: 0 8px;
  border: 0;
  border-radius: 8px;
  font: inherit;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
  transition: background-color 150ms ease, box-shadow 150ms ease, transform 150ms ease;
}

.soft-button {
  color: var(--color-primary);
  background: rgba(43, 94, 162, 0.1);
}

.gray-button {
  color: var(--color-primary);
  background: #d9d9d9;
}

.primary-button {
  color: #fff;
  background: var(--color-primary);
}

.soft-button:hover:not(:disabled),
.gray-button:hover:not(:disabled),
.primary-button:hover:not(:disabled) {
  transform: translateY(-1px);
}

.soft-button:hover:not(:disabled) {
  background: rgba(43, 94, 162, 0.2);
}

.gray-button:hover:not(:disabled) {
  background: #c9d6ea;
}

.primary-button:hover:not(:disabled) {
  background: var(--color-primary-strong);
  box-shadow: 0 4px 10px rgba(43, 94, 162, 0.24);
}

.soft-button:disabled,
.gray-button:disabled,
.primary-button:disabled {
  opacity: 0.55;
  cursor: default;
}

.dataset-card__divider {
  height: 1px;
  margin: 12px 0;
  background: #d9d9d9;
}

.dataset-card__name-row {
  min-height: 38px;
  justify-content: space-between;
  gap: 11px;
}

.dataset-card__title {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.dataset-card__title strong {
  display: -webkit-box;
  overflow: hidden;
  color: #000;
  font-size: 16px;
  font-weight: 800;
  line-height: 1.22;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.dataset-card__title span {
  color: #66758a;
  font-size: 12px;
}

.visibility-button {
  width: 35px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 0;
  border-radius: 6px;
  color: #000;
  background: #d9d9d9;
  cursor: pointer;
  transition: background-color 150ms ease, transform 150ms ease;
}

.visibility-button:hover,
.visibility-button:focus-visible {
  background: #c9c9c9;
  outline: none;
  transform: scale(1.03);
}

.visibility-button .material-symbols-outlined {
  font-size: 19px;
}

.file-tree {
  position: relative;
  min-height: 308px;
  padding: 18px;
  background: #ededed;
}

.file-tree__rows {
  display: grid;
  gap: 13px;
  padding-right: 18px;
}

.file-row {
  min-width: 0;
  height: 24px;
  display: grid;
  grid-template-columns: 15px 24px minmax(0, 1fr) 35px;
  align-items: center;
  gap: 10px;
  padding-left: calc((var(--file-depth, 0) - 1) * 32px);
  color: #000;
  font-size: 16px;
}

.file-row--root {
  grid-template-columns: 24px minmax(0, 1fr) 35px;
  padding-left: 0;
  font-weight: 800;
}

.file-row--hidden {
  color: #b8b8b8;
}

.file-row--hidden .file-row__name {
  opacity: 0.2;
}

.file-row__branch {
  width: 15px;
  color: #000;
}

.file-row__icon {
  color: #555;
  font-size: 24px;
}

.file-row__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-close-button {
  position: absolute;
  right: 20px;
  bottom: 20px;
  min-height: 28px;
  padding: 4px 16px;
  border: 0;
  border-radius: 8px;
  color: #fff;
  background: var(--color-primary);
  font: inherit;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
}

.file-tree__fade {
  pointer-events: none;
  position: absolute;
  left: 7px;
  right: 0;
  bottom: 54px;
  height: 87px;
  background: linear-gradient(to bottom, rgba(237, 237, 237, 0), #ededed);
}

.empty-data-state {
  display: grid;
  place-items: center;
  align-self: start;
  gap: 10px;
  min-height: 240px;
  margin-top: 24px;
  padding: 28px;
  border: 1px dashed rgba(43, 94, 162, 0.24);
  border-radius: 12px;
  color: #66758a;
  text-align: center;
  background: #f7f9fc;
}

.empty-data-state strong,
.empty-data-state p {
  margin: 0;
}

.empty-data-state strong {
  color: #000;
}

.empty-data-state .material-symbols-outlined {
  color: var(--color-primary);
  font-size: 32px;
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
