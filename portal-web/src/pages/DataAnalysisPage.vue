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

/** 채팅 첨부 파일 선택창을 데이터 분석 page 내부 input과 연결합니다. */
function openInteractionPicker() {
  interactionPickerRef.value?.click()
}

/** 데이터 소스 업로드 선택창을 데이터 분석 page 내부 input과 연결합니다. */
function openDatasetPicker() {
  datasetPickerRef.value?.click()
}

defineExpose({
  openDatasetPicker,
  openInteractionPicker,
})
</script>

<template>
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
</template>

<style scoped>
.dataset-picker {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}
</style>
