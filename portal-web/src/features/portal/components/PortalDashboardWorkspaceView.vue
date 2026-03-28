<script setup lang="ts">
import PortalAnalyticsPane from './PortalAnalyticsPane.vue'
import PortalConversationPane from './PortalConversationPane.vue'
import type {
  AnalyticsData,
  AnalyticsPayload,
  ComposerData,
  ConversationData,
  DatasetAsset,
  WorkspacePayload,
} from '../types'

defineProps<{
  conversation: ConversationData
  composer: ComposerData
  shellAnalytics: AnalyticsData
  analyticsPayload: AnalyticsPayload | null
  workspacePayload: WorkspacePayload | null
  activeDataset: DatasetAsset | null
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
  canExportReport: boolean
  pendingAttachmentName: string | null
  pendingAttachmentMeta: string | null
}>()

const emit = defineEmits<{
  attach: []
  dropFile: [file: File]
  removeAttachment: []
  send: [message: string]
  resizeStart: [event: PointerEvent]
  promptClick: [prompt: string]
  toggleFullscreen: []
  exportReport: []
  shareReport: []
}>()
</script>

<template>
  <div
    class="portal-main-grid"
    :class="{
      'portal-main-grid--resizing': isResizingAnalyticsPane,
      'portal-main-grid--analytics-fullscreen': isAnalyticsFullscreen,
    }"
    :style="{ '--analytics-pane-width': `${analyticsPaneWidth}px` }"
  >
    <PortalConversationPane
      :conversation="conversation"
      :composer="composer"
      :send-disabled="isSending || isRunningAnalysis"
      :attach-disabled="isUploading || isRunningAnalysis"
      :error-message="chatError || uploadError"
      :attached-file-name="pendingAttachmentName"
      :attached-file-meta="pendingAttachmentMeta"
      @attach="emit('attach')"
      @drop-file="(file) => emit('dropFile', file)"
      @remove-attachment="emit('removeAttachment')"
      @send="(message) => emit('send', message)"
    />
    <button class="pane-resizer" type="button" aria-label="분석 패널 너비 조절" @pointerdown="(event) => emit('resizeStart', event)">
      <span></span>
    </button>
    <PortalAnalyticsPane
      :analytics="shellAnalytics"
      :analytics-payload="analyticsPayload"
      :workspace-payload="workspacePayload"
      :dataset-asset="activeDataset"
      :is-loading="isSending || isUploading || isRunningAnalysis"
      :error-message="analyticsError"
      :is-fullscreen="isAnalyticsFullscreen"
      :export-disabled="!canExportReport"
      :share-disabled="!canExportReport"
      @prompt-click="(prompt) => emit('promptClick', prompt)"
      @toggle-fullscreen="emit('toggleFullscreen')"
      @export-report="emit('exportReport')"
      @share-report="emit('shareReport')"
    />
  </div>
</template>

<style scoped>
.portal-main-grid {
  min-height: 0;
  height: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 20px minmax(320px, var(--analytics-pane-width, 420px));
  grid-template-rows: minmax(0, 1fr);
  gap: 0;
  align-items: stretch;
}

.portal-main-grid :deep(.conversation-shell),
.portal-main-grid :deep(.analytics-shell) {
  min-height: 0;
  height: 100%;
}

.portal-main-grid--resizing {
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

.portal-main-grid--analytics-fullscreen {
  grid-template-columns: minmax(0, 1fr);
}

.portal-main-grid--analytics-fullscreen :deep(.conversation-shell),
.portal-main-grid--analytics-fullscreen .pane-resizer {
  display: none;
}

@media (max-width: 1280px) {
  .portal-main-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 20px;
  }

  .pane-resizer {
    display: none;
  }
}
</style>
