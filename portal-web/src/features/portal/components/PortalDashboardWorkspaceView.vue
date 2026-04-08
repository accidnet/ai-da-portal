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
  isCompactLayout: boolean
  isAnalyticsPanelOpen: boolean
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
  closeAnalyticsPanel: []
}>()
</script>

<template>
  <div
    class="portal-main-grid"
    :class="{
      'portal-main-grid--resizing': isResizingAnalyticsPane,
      'portal-main-grid--analytics-fullscreen': isAnalyticsFullscreen,
      'portal-main-grid--compact': isCompactLayout,
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
    <div
      class="analytics-panel-shell"
      :class="{
        'analytics-panel-shell--compact': isCompactLayout,
        'analytics-panel-shell--open': isAnalyticsPanelOpen,
      }"
    >
      <div v-if="isCompactLayout" class="analytics-panel-header">
        <strong>시각화 패널</strong>
        <button type="button" class="analytics-panel-close" @click="emit('closeAnalyticsPanel')">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>

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

    <div v-if="isCompactLayout && isAnalyticsPanelOpen" class="analytics-panel-backdrop" @click="emit('closeAnalyticsPanel')"></div>
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
.portal-main-grid :deep(.analytics-shell),
.analytics-panel-shell {
  min-height: 0;
  height: 100%;
}

.analytics-panel-shell {
  min-width: 0;
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

.analytics-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding: 0 4px;
}

.analytics-panel-header strong {
  color: var(--color-primary-strong);
  font-size: 0.95rem;
}

.analytics-panel-close {
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

.analytics-panel-backdrop {
  position: fixed;
  inset: 0;
  z-index: 11;
  background: rgba(15, 23, 42, 0.28);
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

@media (max-width: 960px) {
  .portal-main-grid--compact {
    position: relative;
    display: block;
  }

  .portal-main-grid--compact .analytics-panel-shell {
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

  .portal-main-grid--compact .analytics-panel-shell--open {
    transform: translateX(0);
  }
}
</style>
