<script setup lang="ts">
import { ref } from 'vue'
import { RouterView } from 'vue-router'

import type { UploadPickerMode } from '@/features/data-source/types'
import type {
  AnalyticsData,
  AnalyticsPayload,
  AnalysisScreen,
  ComposerData,
  ConversationData,
  DatasetAsset,
  DatasetLibraryItem,
  WorkspacePayload,
} from '@/features/data-analysis/types'

defineProps<{
  analyticsPaneWidth: number
  isResizingAnalyticsPane: boolean
  isAnalyticsFullscreen: boolean
  isCompactLayout: boolean
  isAnalyticsPanelOpen: boolean
  shellAnalytics: AnalyticsData
  currentScreen: AnalysisScreen
  activeSessionId: string | null
  authError: string | null
  exportMessage: string | null
  conversation: ConversationData
  composer: ComposerData
  analyticsPayload: AnalyticsPayload | null
  workspacePayload: WorkspacePayload | null
  isSending: boolean
  isUploading: boolean
  isRunningAnalysis: boolean
  isSendingInteraction: boolean
  chatError: string | null
  uploadError: string | null
  analyticsError: string | null
  canExportReport: boolean
  connectedDatasets: DatasetAsset[]
  isSessionMutating: boolean
  datasetsLibrary: DatasetLibraryItem[]
  selectedDatasetId: string | null
  datasetLibrarySearchQuery: string
  datasetLibraryError: string | null
  isDatasetMutating: boolean
}>()

const datasetPickerRef = ref<HTMLInputElement | null>(null)

const emit = defineEmits<{
  toggleSidebarPanel: []
  toggleAnalyticsPanel: []
  datasetLibrarySearchChange: [value: string]
  selectDataset: [datasetId: string]
  attachDataset: [datasetId: string]
  detachDataset: [datasetId: string]
  deleteDataset: [datasetId: string]
  datasetFileChange: [event: Event]
  send: [message: string]
  analyticsResizeStart: [event: PointerEvent]
  toggleFullscreen: []
  exportReport: []
  shareReport: []
  closeAnalyticsPanel: []
}>()

/** 현재 main route page의 데이터 직접 업로드 선택창을 엽니다. */
function openDatasetPicker(mode: UploadPickerMode = 'files') {
  const picker = datasetPickerRef.value
  if (!picker) return

  picker.value = ''
  picker.multiple = true
  picker.removeAttribute('accept')
  picker.removeAttribute('webkitdirectory')
  picker.removeAttribute('directory')

  if (mode === 'folder') {
    picker.setAttribute('webkitdirectory', '')
    picker.setAttribute('directory', '')
  }

  picker.click()
}

defineExpose({
  openDatasetPicker,
})
</script>

<template>
  <main class="analysis-main-shell">
    <div v-if="isCompactLayout" class="analysis-mobile-toolbar">
      <button type="button" class="analysis-mobile-toolbar__button" @click="emit('toggleSidebarPanel')">
        <span class="material-symbols-outlined">menu_open</span>
        <span>좌측 패널</span>
      </button>
      <button
        v-if="currentScreen === 'dashboard'"
        type="button"
        class="analysis-mobile-toolbar__button"
        @click="emit('toggleAnalyticsPanel')"
      >
        <span class="material-symbols-outlined">bar_chart</span>
        <span>시각화 패널</span>
      </button>
    </div>

    <div v-if="authError || exportMessage" class="analysis-status-messages">
      <p v-if="authError" class="auth-error">{{ authError }}</p>
      <p v-if="exportMessage" class="export-message">{{ exportMessage }}</p>
    </div>

    <div class="analysis-screen-shell">
      <RouterView v-slot="{ Component }">
        <component
          :is="Component"
          :analytics-pane-width="analyticsPaneWidth"
          :is-resizing-analytics-pane="isResizingAnalyticsPane"
          :is-analytics-fullscreen="isAnalyticsFullscreen"
          :is-compact-layout="isCompactLayout"
          :is-analytics-panel-open="isAnalyticsPanelOpen"
          :shell-analytics="shellAnalytics"
          :current-screen="currentScreen"
          :active-session-id="activeSessionId"
          :conversation="conversation"
          :composer="composer"
          :analytics-payload="analyticsPayload"
          :workspace-payload="workspacePayload"
          :is-sending="isSending"
          :is-uploading="isUploading"
          :is-running-analysis="isRunningAnalysis"
          :is-sending-interaction="isSendingInteraction"
          :chat-error="chatError"
          :upload-error="uploadError"
          :analytics-error="analyticsError"
          :can-export-report="canExportReport"
          :connected-datasets="connectedDatasets"
          :is-session-mutating="isSessionMutating"
          :datasets-library="datasetsLibrary"
          :selected-dataset-id="selectedDatasetId"
          :dataset-library-search-query="datasetLibrarySearchQuery"
          :dataset-library-error="datasetLibraryError"
          :is-dataset-mutating="isDatasetMutating"
          @upload-dataset="(mode?: UploadPickerMode) => openDatasetPicker(mode)"
          @dataset-library-search-change="(value: string) => emit('datasetLibrarySearchChange', value)"
          @select-dataset="(datasetId: string) => emit('selectDataset', datasetId)"
          @attach-dataset="(datasetId: string) => emit('attachDataset', datasetId)"
          @detach-dataset="(datasetId: string) => emit('detachDataset', datasetId)"
          @delete-dataset="(datasetId: string) => emit('deleteDataset', datasetId)"
          @dataset-file-change="(event: Event) => emit('datasetFileChange', event)"
          @send="(message: string) => emit('send', message)"
          @analytics-resize-start="(event: PointerEvent) => emit('analyticsResizeStart', event)"
          @toggle-fullscreen="emit('toggleFullscreen')"
          @export-report="emit('exportReport')"
          @share-report="emit('shareReport')"
          @close-analytics-panel="emit('closeAnalyticsPanel')"
        />
      </RouterView>
    </div>

    <input
      ref="datasetPickerRef"
      class="dataset-picker"
      type="file"
      multiple
      @change="(event) => emit('datasetFileChange', event)"
    />
  </main>
</template>

<style scoped>
.analysis-main-shell {
  min-width: 0;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
}

.analysis-mobile-toolbar {
  display: flex;
  gap: 10px;
}

.analysis-mobile-toolbar__button {
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  color: var(--color-primary-strong);
  background: rgba(255, 255, 255, 0.92);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.analysis-status-messages {
  display: grid;
  gap: 8px;
}

.analysis-screen-shell {
  min-height: 0;
  height: 100%;
  flex: 1;
  display: grid;
  gap: 18px;
  overflow: hidden;
}

.auth-error,
.export-message {
  margin: 0 4px;
  padding-top: 2px;
  font-size: 0.86rem;
  line-height: 1.5;
}

.auth-error {
  color: #9b3b3b;
}

.export-message {
  color: #1d6b45;
}

.dataset-picker {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

@media (max-width: 960px) {
  .analysis-main-shell,
  .analysis-screen-shell {
    overflow: visible;
  }

  .analysis-mobile-toolbar {
    flex-wrap: wrap;
  }
}
</style>
