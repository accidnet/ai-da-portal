<script setup lang="ts">
import AnalysisConversationPane from './AnalysisConversationPane.vue'
import AnalysisRightPane from './AnalysisRightPane.vue'
import type {
  AnalyticsData,
  AnalyticsPayload,
  ComposerData,
  ConversationData,
  WorkspacePayload,
} from '../types'

defineProps<{
  conversation: ConversationData
  composer: ComposerData
  shellAnalytics: AnalyticsData
  analyticsPayload: AnalyticsPayload | null
  workspacePayload: WorkspacePayload | null
  isResizingAnalyticsPane: boolean
  isAnalyticsFullscreen: boolean
  analyticsPaneWidth: number
  isSending: boolean
  isUploading: boolean
  isRunningAnalysis: boolean
  isSendingInteraction: boolean
  chatError: string | null
  uploadError: string | null
  analyticsError: string | null
  isCompactLayout: boolean
  isAnalyticsPanelOpen: boolean
  canExportReport: boolean
  pendingAttachmentName: string | null
  pendingAttachmentMeta: string | null
}>()

const emit = defineEmits<{
  attach: []
  dropFile: [files: File[]]
  removeAttachment: []
  send: [message: string]
  resizeStart: [event: PointerEvent]
  toggleFullscreen: []
  exportReport: []
  shareReport: []
  closeAnalyticsPanel: []
}>()
</script>

<template>
  <div
    class="analysis-workspace-grid"
    :class="{
      'analysis-workspace-grid--resizing': isResizingAnalyticsPane,
      'analysis-workspace-grid--analytics-fullscreen': isAnalyticsFullscreen,
      'analysis-workspace-grid--compact': isCompactLayout,
    }"
    :style="{ '--analytics-pane-width': `${analyticsPaneWidth}px` }"
  >
    <AnalysisConversationPane
      :conversation="conversation"
      :composer="composer"
      :send-disabled="isSending || isRunningAnalysis"
      :attach-disabled="isUploading || isRunningAnalysis"
      :error-message="chatError || uploadError"
      :attached-file-name="pendingAttachmentName"
      :attached-file-meta="pendingAttachmentMeta"
      @attach="emit('attach')"
      @drop-file="(files) => emit('dropFile', files)"
      @remove-attachment="emit('removeAttachment')"
      @send="(message) => emit('send', message)"
    />
    <button class="pane-resizer" type="button" aria-label="분석 패널 너비 조절" @pointerdown="(event) => emit('resizeStart', event)">
      <span></span>
    </button>
    <AnalysisRightPane
      :shell-analytics="shellAnalytics"
      :analytics-payload="analyticsPayload"
      :workspace-payload="workspacePayload"
      :is-compact-layout="isCompactLayout"
      :is-analytics-panel-open="isAnalyticsPanelOpen"
      :is-analytics-fullscreen="isAnalyticsFullscreen"
      :is-loading="isSending || isUploading || isRunningAnalysis"
      :analytics-error="analyticsError"
      :can-export-report="canExportReport"
      @toggle-fullscreen="emit('toggleFullscreen')"
      @export-report="emit('exportReport')"
      @share-report="emit('shareReport')"
      @close-analytics-panel="emit('closeAnalyticsPanel')"
    />
  </div>
</template>

<style scoped>
.analysis-workspace-grid {
  min-height: 0;
  height: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 20px minmax(320px, var(--analytics-pane-width, 420px));
  grid-template-rows: minmax(0, 1fr);
  gap: 0;
  align-items: stretch;
}

.analysis-workspace-grid :deep(.conversation-shell),
.analysis-workspace-grid :deep(.analytics-shell),
.analysis-workspace-grid :deep(.analysis-right-pane) {
  min-height: 0;
  height: 100%;
}

.analysis-workspace-grid--resizing {
  user-select: none;
  cursor: col-resize;
}

.pane-resizer {
  position: relative;
  width: 20px;
  height: 100%;
  cursor: col-resize;
}

.pane-resizer span {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 3px;
  height: 3px;
  border-radius: 999px;
  transform: translate(-50%, -50%);
  background: rgba(24, 74, 140, 0.22);
  box-shadow:
    0 -7px 0 rgba(24, 74, 140, 0.22),
    0 7px 0 rgba(24, 74, 140, 0.22);
}

.analysis-workspace-grid--analytics-fullscreen {
  grid-template-columns: minmax(0, 1fr);
}

.analysis-workspace-grid--analytics-fullscreen :deep(.conversation-shell),
.analysis-workspace-grid--analytics-fullscreen .pane-resizer {
  display: none;
}

@media (max-width: 1280px) {
  .analysis-workspace-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 20px;
  }

  .pane-resizer {
    display: none;
  }
}

@media (max-width: 960px) {
  .analysis-workspace-grid--compact {
    position: relative;
    display: block;
  }
}
</style>
