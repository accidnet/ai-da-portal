<script setup lang="ts">
import { ref } from 'vue'

import AnalysisWorkspaceView from '@/features/data-analysis/components/AnalysisWorkspaceView.vue'
import DatasetLibrary from '@/features/data-analysis/components/DatasetLibrary.vue'
import SessionHub from '@/features/data-analysis/components/SessionHub.vue'
import type {
  AnalyticsData,
  AnalyticsPayload,
  AnalysisScreen,
  ComposerData,
  ConversationData,
  DatasetLibraryItem,
  SessionItem,
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
  pendingAttachmentName: string | null
  pendingAttachmentMeta: string | null
  sessionSummaries: SessionItem[]
  sessionHubSearchQuery: string
  sessionHubError: string | null
  isSessionMutating: boolean
  datasetsLibrary: DatasetLibraryItem[]
  selectedDatasetId: string | null
  datasetLibrarySearchQuery: string
  datasetLibraryError: string | null
  isDatasetMutating: boolean
}>()

const emit = defineEmits<{
  toggleSidebarPanel: []
  toggleAnalyticsPanel: []
  sessionHubSearchChange: [value: string]
  openSession: [sessionId: string]
  renameSession: [payload: { sessionId: string; title: string }]
  createSession: []
  deleteSession: [sessionId: string]
  datasetLibrarySearchChange: [value: string]
  selectDataset: [datasetId: string]
  attachDataset: [datasetId: string]
  detachDataset: [datasetId: string]
  deleteDataset: [datasetId: string]
  interactionFileChange: [event: Event]
  datasetFileChange: [event: Event]
  dropFile: [files: File[]]
  removeAttachment: []
  send: [message: string]
  analyticsResizeStart: [event: PointerEvent]
  toggleFullscreen: []
  exportReport: []
  shareReport: []
  closeAnalyticsPanel: []
}>()

const interactionPickerRef = ref<HTMLInputElement | null>(null)
const datasetPickerRef = ref<HTMLInputElement | null>(null)

/** 채팅 첨부 파일 선택창을 메인 layout 내부 input과 연결합니다. */
function openInteractionPicker() {
  interactionPickerRef.value?.click()
}

/** 데이터 소스 업로드 선택창을 메인 layout 내부 input과 연결합니다. */
function openDatasetPicker() {
  datasetPickerRef.value?.click()
}

defineExpose({
  openDatasetPicker,
  openInteractionPicker,
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
      <AnalysisWorkspaceView
        v-if="currentScreen === 'dashboard'"
        :conversation="conversation"
        :composer="composer"
        :shell-analytics="shellAnalytics"
        :analytics-payload="analyticsPayload"
        :workspace-payload="workspacePayload"
        :is-resizing-analytics-pane="isResizingAnalyticsPane"
        :is-analytics-fullscreen="isAnalyticsFullscreen"
        :analytics-pane-width="analyticsPaneWidth"
        :is-sending="isSending"
        :is-uploading="isUploading"
        :is-running-analysis="isRunningAnalysis"
        :is-sending-interaction="isSendingInteraction"
        :chat-error="chatError"
        :upload-error="uploadError"
        :analytics-error="analyticsError"
        :is-compact-layout="isCompactLayout"
        :is-analytics-panel-open="isAnalyticsPanelOpen"
        :can-export-report="canExportReport"
        :pending-attachment-name="pendingAttachmentName"
        :pending-attachment-meta="pendingAttachmentMeta"
        @attach="openInteractionPicker"
        @drop-file="(files) => emit('dropFile', files)"
        @remove-attachment="emit('removeAttachment')"
        @send="(message) => emit('send', message)"
        @resize-start="(event) => emit('analyticsResizeStart', event)"
        @toggle-fullscreen="emit('toggleFullscreen')"
        @export-report="emit('exportReport')"
        @share-report="emit('shareReport')"
        @close-analytics-panel="emit('closeAnalyticsPanel')"
      />

      <SessionHub
        v-else-if="currentScreen === 'sessions'"
        :sessions="sessionSummaries"
        :active-session-id="activeSessionId"
        :search-query="sessionHubSearchQuery"
        :is-busy="isSessionMutating"
        :error-message="sessionHubError"
        @search-change="(value) => emit('sessionHubSearchChange', value)"
        @open-session="(sessionId) => emit('openSession', sessionId)"
        @rename-session="(payload) => emit('renameSession', payload)"
        @delete-session="(sessionId) => emit('deleteSession', sessionId)"
        @create-session="emit('createSession')"
      />

      <DatasetLibrary
        v-else
        :datasets="datasetsLibrary"
        :selected-dataset-id="selectedDatasetId"
        :active-session-id="activeSessionId"
        :search-query="datasetLibrarySearchQuery"
        :is-busy="isDatasetMutating"
        :error-message="datasetLibraryError"
        @search-change="(value) => emit('datasetLibrarySearchChange', value)"
        @upload-file="openDatasetPicker"
        @select-dataset="(datasetId) => emit('selectDataset', datasetId)"
        @attach-dataset="(datasetId) => emit('attachDataset', datasetId)"
        @detach-dataset="(datasetId) => emit('detachDataset', datasetId)"
        @delete-dataset="(datasetId) => emit('deleteDataset', datasetId)"
      />
    </div>

    <input
      ref="interactionPickerRef"
      class="dataset-picker"
      type="file"
      multiple
      accept=".csv,.tsv,.xls,.xlsx,.json,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      @change="(event) => emit('interactionFileChange', event)"
    />
    <input
      ref="datasetPickerRef"
      class="dataset-picker"
      type="file"
      accept=".csv,.tsv,.xls,.xlsx,.json,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
