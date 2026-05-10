<script setup lang="ts">
import { ref } from 'vue'

import AnalysisSidebar from '@/features/data-analysis/components/AnalysisSidebar.vue'
import AnalysisWorkspaceView from '@/features/data-analysis/components/AnalysisWorkspaceView.vue'
import DatasetLibrary from '@/features/data-analysis/components/DatasetLibrary.vue'
import SessionHub from '@/features/data-analysis/components/SessionHub.vue'
import type {
  AnalyticsData,
  AnalyticsPayload,
  AnalysisScreen,
  BackendConnectionStatus,
  ComposerData,
  ConversationData,
  DatasetLibraryItem,
  OpenAiAuthStatus,
  SessionItem,
  SharedAnalysisSnapshot,
  SidebarData,
  WorkspacePayload,
} from '@/features/data-analysis/types'

defineProps<{
  sidebarWidth: number
  isResizingSidebar: boolean
  analyticsPaneWidth: number
  isResizingAnalyticsPane: boolean
  isAnalyticsFullscreen: boolean
  isCompactLayout: boolean
  isSidebarOpen: boolean
  isAnalyticsPanelOpen: boolean
  shellSidebar: SidebarData
  shellAnalytics: AnalyticsData
  recentSessions: SessionItem[]
  currentScreen: AnalysisScreen
  activeSessionId: string | null
  connectionStatus: BackendConnectionStatus
  authStatus: OpenAiAuthStatus
  isConnecting: boolean
  isDisconnecting: boolean
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
  isHelpDialogOpen: boolean
  sharedAnalysis: SharedAnalysisSnapshot | null
  sharedAnalysisCreatedAtLabel: string
}>()

const emit = defineEmits<{
  primaryAction: [screen: AnalysisScreen]
  createSession: []
  connectOpenAi: []
  disconnectOpenAi: []
  openHelp: []
  selectSession: [sessionId: string]
  deleteSession: [sessionId: string]
  sidebarResizeStart: [event: PointerEvent]
  toggleSidebarPanel: []
  toggleAnalyticsPanel: []
  sessionHubSearchChange: [value: string]
  openSession: [sessionId: string]
  renameSession: [payload: { sessionId: string; title: string }]
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
  closeSidebarPanel: []
  closeHelpDialog: []
  closeSharedAnalysisDialog: []
  previewSharedAnalysis: []
}>()

const interactionPickerRef = ref<HTMLInputElement | null>(null)
const datasetPickerRef = ref<HTMLInputElement | null>(null)

/** 채팅 첨부 파일 선택창을 layout 내부 input과 연결합니다. */
function openInteractionPicker() {
  interactionPickerRef.value?.click()
}

/** 데이터 소스 업로드 선택창을 layout 내부 input과 연결합니다. */
function openDatasetPicker() {
  datasetPickerRef.value?.click()
}

defineExpose({
  openDatasetPicker,
  openInteractionPicker,
})
</script>

<template>
  <div class="analysis-layout" :style="{ '--sidebar-width': `${sidebarWidth}px` }">
    <aside
      class="analysis-sidebar-shell"
      :class="{
        'analysis-sidebar-shell--compact': isCompactLayout,
        'analysis-sidebar-shell--open': isSidebarOpen,
      }"
    >
      <div v-if="isCompactLayout" class="mobile-panel-header">
        <strong>메뉴</strong>
        <button type="button" class="mobile-panel-close" @click="emit('closeSidebarPanel')">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>

      <AnalysisSidebar
        :sidebar="{ ...shellSidebar, recentSessions }"
        :active-screen="currentScreen"
        :active-session-id="activeSessionId"
        :connection-status="connectionStatus"
        :auth-status="authStatus"
        :is-connecting="isConnecting"
        :is-disconnecting="isDisconnecting"
        @primary-action="(screen) => emit('primaryAction', screen)"
        @create-session="emit('createSession')"
        @connect-open-ai="emit('connectOpenAi')"
        @disconnect-open-ai="emit('disconnectOpenAi')"
        @open-help="emit('openHelp')"
        @select-session="(sessionId) => emit('selectSession', sessionId)"
        @delete-session="(sessionId) => emit('deleteSession', sessionId)"
      />
    </aside>

    <button
      class="page-pane-resizer"
      :class="{ 'page-pane-resizer--active': isResizingSidebar }"
      type="button"
      aria-label="사이드바 너비 조절"
      @pointerdown="(event) => emit('sidebarResizeStart', event)"
    >
      <span></span>
    </button>

    <div class="analysis-main-shell">
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

    <div v-if="isHelpDialogOpen" class="analysis-overlay" @click.self="emit('closeHelpDialog')">
      <section class="analysis-dialog">
        <header class="analysis-dialog__header">
          <div>
            <p>도움말</p>
            <h2>AI 데이터 분석 사용 안내</h2>
          </div>
          <button type="button" class="dialog-close" @click="emit('closeHelpDialog')">
            <span class="material-symbols-outlined">close</span>
          </button>
        </header>
        <ul class="help-list">
          <li>좌측의 <strong>새로운 분석</strong>을 누른 뒤 첫 메시지를 보내면 새 세션이 생성됩니다.</li>
          <li>데이터 소스 화면에서 파일 업로드 후 활성 세션에 바로 연결할 수 있습니다.</li>
          <li>오른쪽 작업공간의 <strong>공유</strong>는 현재 브라우저 기반 링크 복사, <strong>미리보기</strong>는 새 탭 리포트 열기입니다.</li>
          <li>ChatGPT 연결은 좌측 하단에서 바로 진행할 수 있습니다.</li>
        </ul>
      </section>
    </div>

    <div v-if="sharedAnalysis" class="analysis-overlay" @click.self="emit('closeSharedAnalysisDialog')">
      <section class="analysis-dialog analysis-dialog--wide">
        <header class="analysis-dialog__header">
          <div>
            <p>공유 미리보기</p>
            <h2>{{ sharedAnalysis.title }}</h2>
            <span class="dialog-subtext">생성 시각 {{ sharedAnalysisCreatedAtLabel }}</span>
          </div>
          <button type="button" class="dialog-close" @click="emit('closeSharedAnalysisDialog')">
            <span class="material-symbols-outlined">close</span>
          </button>
        </header>
        <pre class="shared-preview">{{ sharedAnalysis.content }}</pre>
        <div class="dialog-actions">
          <button type="button" class="dialog-button dialog-button--primary" @click="emit('previewSharedAnalysis')">새 탭 미리보기</button>
          <button type="button" class="dialog-button" @click="emit('closeSharedAnalysisDialog')">닫기</button>
        </div>
      </section>
    </div>

    <div v-if="isCompactLayout && isSidebarOpen" class="mobile-panel-backdrop" @click="emit('closeSidebarPanel')"></div>
  </div>
</template>

<style scoped>
.analysis-layout {
  position: relative;
  height: 100vh;
  display: grid;
  grid-template-columns: minmax(248px, var(--sidebar-width, 288px)) 20px minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr);
  gap: 0;
  padding: 24px;
  overflow: hidden;
}

.page-pane-resizer {
  position: relative;
  width: 20px;
  height: 100%;
  cursor: col-resize;
}

.page-pane-resizer span {
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

.analysis-main-shell {
  min-width: 0;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
}

.analysis-sidebar-shell {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.analysis-sidebar-shell :deep(.sidebar-card) {
  flex: 1 1 auto;
  height: auto;
}

.analysis-mobile-toolbar {
  display: flex;
  gap: 10px;
}

.analysis-mobile-toolbar__button,
.mobile-panel-close {
  border: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.92);
  color: var(--color-primary-strong);
  font: inherit;
}

.analysis-mobile-toolbar__button {
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  border-radius: 14px;
  font-weight: 700;
  cursor: pointer;
}

.mobile-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding: 0 4px;
}

.mobile-panel-header strong {
  color: var(--color-primary-strong);
  font-size: 0.95rem;
}

.mobile-panel-close {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  cursor: pointer;
}

.mobile-panel-backdrop {
  position: fixed;
  inset: 0;
  z-index: 11;
  background: rgba(15, 23, 42, 0.28);
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

.analysis-overlay {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.34);
}

.analysis-dialog {
  width: min(560px, 100%);
  max-height: min(80vh, 720px);
  display: grid;
  gap: 18px;
  overflow: auto;
  padding: 24px;
  border-radius: 24px;
  background: #fff;
  box-shadow: 0 24px 56px rgba(15, 23, 42, 0.18);
}

.analysis-dialog--wide {
  width: min(880px, 100%);
}

.analysis-dialog__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.analysis-dialog__header p,
.help-list,
.dialog-subtext {
  margin: 0;
  color: var(--color-text-muted);
}

.analysis-dialog__header p {
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.7rem;
  font-weight: 800;
}

.analysis-dialog__header h2 {
  margin: 8px 0 0;
  font-family: var(--font-heading);
}

.dialog-close,
.dialog-button {
  border: 1px solid var(--color-border);
  border-radius: 14px;
  background: var(--color-surface-muted);
  font: inherit;
}

.dialog-close {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.help-list {
  display: grid;
  gap: 12px;
  padding-left: 18px;
  line-height: 1.6;
}

.shared-preview {
  margin: 0;
  padding: 18px;
  border-radius: 18px;
  background: var(--color-surface-muted);
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  line-height: 1.6;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.dialog-button {
  min-height: 42px;
  padding: 0 16px;
  cursor: pointer;
}

.dialog-button--primary {
  color: #fff;
  border-color: var(--color-primary);
  background: var(--color-primary);
}

@media (max-width: 1280px) {
  .analysis-layout {
    padding: 20px;
  }
}

@media (max-width: 960px) {
  .analysis-layout {
    grid-template-columns: minmax(0, 1fr);
    padding: 16px;
    height: auto;
    min-height: 100vh;
    overflow: auto;
  }

  .page-pane-resizer {
    display: none;
  }

  .analysis-sidebar-shell {
    position: fixed;
    top: 16px;
    left: 16px;
    bottom: 16px;
    z-index: 12;
    width: min(320px, calc(100vw - 32px));
    padding: 14px;
    border-radius: 24px;
    background: rgba(245, 247, 251, 0.96);
    box-shadow: 0 24px 56px rgba(15, 23, 42, 0.18);
    transform: translateX(calc(-100% - 24px));
    transition: transform 220ms ease;
  }

  .analysis-sidebar-shell--open {
    transform: translateX(0);
  }

  .analysis-main-shell,
  .analysis-screen-shell {
    overflow: visible;
  }

  .analysis-mobile-toolbar {
    flex-wrap: wrap;
  }

  .analysis-overlay {
    padding: 16px;
  }
}
</style>
