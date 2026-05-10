<script setup lang="ts">
import { shallowRef } from 'vue'
import { RouterView } from 'vue-router'

import type {
  AnalyticsData,
  AnalyticsPayload,
  AnalysisScreen,
  ComposerData,
  ConversationData,
  DatasetAsset,
  DatasetLibraryItem,
  SessionItem,
  WorkspacePayload,
} from '@/features/data-analysis/types'

type RoutedPortalPage = {
  openDatasetPicker?: () => void
  openInteractionPicker?: () => void
}

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
  connectedDatasets: DatasetAsset[]
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
  uploadDataset: []
}>()

const routedPageRef = shallowRef<RoutedPortalPage | null>(null)

/** 현재 main route page의 데이터셋 업로드 선택창을 엽니다. */
function openDatasetPicker() {
  routedPageRef.value?.openDatasetPicker?.()
}

/** 현재 main route page의 채팅 첨부 선택창을 엽니다. */
function openInteractionPicker() {
  routedPageRef.value?.openInteractionPicker?.()
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
      <RouterView v-slot="{ Component }">
        <component
          :is="Component"
          ref="routedPageRef"
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
          :pending-attachment-name="pendingAttachmentName"
          :pending-attachment-meta="pendingAttachmentMeta"
          :connected-datasets="connectedDatasets"
          :session-summaries="sessionSummaries"
          :session-hub-search-query="sessionHubSearchQuery"
          :session-hub-error="sessionHubError"
          :is-session-mutating="isSessionMutating"
          :datasets-library="datasetsLibrary"
          :selected-dataset-id="selectedDatasetId"
          :dataset-library-search-query="datasetLibrarySearchQuery"
          :dataset-library-error="datasetLibraryError"
          :is-dataset-mutating="isDatasetMutating"
          @upload-dataset="emit('uploadDataset')"
          @session-hub-search-change="(value: string) => emit('sessionHubSearchChange', value)"
          @open-session="(sessionId: string) => emit('openSession', sessionId)"
          @rename-session="(payload: { sessionId: string; title: string }) => emit('renameSession', payload)"
          @create-session="emit('createSession')"
          @delete-session="(sessionId: string) => emit('deleteSession', sessionId)"
          @dataset-library-search-change="(value: string) => emit('datasetLibrarySearchChange', value)"
          @select-dataset="(datasetId: string) => emit('selectDataset', datasetId)"
          @attach-dataset="(datasetId: string) => emit('attachDataset', datasetId)"
          @detach-dataset="(datasetId: string) => emit('detachDataset', datasetId)"
          @delete-dataset="(datasetId: string) => emit('deleteDataset', datasetId)"
          @interaction-file-change="(event: Event) => emit('interactionFileChange', event)"
          @dataset-file-change="(event: Event) => emit('datasetFileChange', event)"
          @drop-file="(files: File[]) => emit('dropFile', files)"
          @remove-attachment="emit('removeAttachment')"
          @send="(message: string) => emit('send', message)"
          @analytics-resize-start="(event: PointerEvent) => emit('analyticsResizeStart', event)"
          @toggle-fullscreen="emit('toggleFullscreen')"
          @export-report="emit('exportReport')"
          @share-report="emit('shareReport')"
          @close-analytics-panel="emit('closeAnalyticsPanel')"
        />
      </RouterView>
    </div>
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
