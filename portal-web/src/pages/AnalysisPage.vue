<script setup lang="ts">
import AnalysisWorkspaceView from '@/features/data-analysis/components/analysis-workspace-view/AnalysisWorkspaceView.vue'
import DefaultAnalysisView from '@/features/data-analysis/components/default-analysis-view/DefaultAnalysisView.vue'
import type {
  AnalyticsData,
  AnalyticsPayload,
  ComposerData,
  ConversationData,
  DatasetAsset,
  DatasetLibraryItem,
  WorkspacePayload,
} from '@/features/data-analysis/types'
import type { PortalAnalysisViewMode } from '@/layouts/portal/types'

defineProps<{
  analyticsPaneWidth: number
  isResizingAnalyticsPane: boolean
  isAnalyticsFullscreen: boolean
  isCompactLayout: boolean
  isAnalyticsPanelOpen: boolean
  shellAnalytics: AnalyticsData
  analysisViewMode?: PortalAnalysisViewMode
  activeWorkspaceId?: string | null
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
  datasetsLibrary: DatasetLibraryItem[]
  isDatasetMutating: boolean
}>()

const emit = defineEmits<{
  send: [message: string]
  analyticsResizeStart: [event: PointerEvent]
  toggleFullscreen: []
  exportReport: []
  shareReport: []
  closeAnalyticsPanel: []
  uploadDataset: []
  attachDataset: [datasetId: string]
  selectDataset: [datasetId: string]
  detachDataset: [datasetId: string]
  detachDatasets: [datasetIds: string[]]
}>()
</script>

<template>
  <DefaultAnalysisView
    v-if="(analysisViewMode ?? 'default') === 'default'"
    :conversation="conversation"
    :composer="composer"
    :shell-analytics="shellAnalytics"
    :active-workspace-id="null"
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
    :connected-datasets="connectedDatasets"
    :datasets-library="datasetsLibrary"
    :is-dataset-mutating="isDatasetMutating"
    @send="(message) => emit('send', message)"
    @resize-start="(event) => emit('analyticsResizeStart', event)"
    @toggle-fullscreen="emit('toggleFullscreen')"
    @export-report="emit('exportReport')"
    @share-report="emit('shareReport')"
    @close-analytics-panel="emit('closeAnalyticsPanel')"
    @upload-dataset="emit('uploadDataset')"
    @attach-dataset="(datasetId) => emit('attachDataset', datasetId)"
    @select-dataset="(datasetId) => emit('selectDataset', datasetId)"
    @detach-dataset="(datasetId) => emit('detachDataset', datasetId)"
    @detach-datasets="(datasetIds) => emit('detachDatasets', datasetIds)"
  />
  <AnalysisWorkspaceView
    v-else
    :conversation="conversation"
    :composer="composer"
    :shell-analytics="shellAnalytics"
    :active-workspace-id="activeWorkspaceId ?? null"
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
    :connected-datasets="connectedDatasets"
    :datasets-library="datasetsLibrary"
    :is-dataset-mutating="isDatasetMutating"
    @send="(message) => emit('send', message)"
    @resize-start="(event) => emit('analyticsResizeStart', event)"
    @toggle-fullscreen="emit('toggleFullscreen')"
    @export-report="emit('exportReport')"
    @share-report="emit('shareReport')"
    @close-analytics-panel="emit('closeAnalyticsPanel')"
    @upload-dataset="emit('uploadDataset')"
    @attach-dataset="(datasetId) => emit('attachDataset', datasetId)"
    @select-dataset="(datasetId) => emit('selectDataset', datasetId)"
    @detach-dataset="(datasetId) => emit('detachDataset', datasetId)"
    @detach-datasets="(datasetIds) => emit('detachDatasets', datasetIds)"
  />
</template>
