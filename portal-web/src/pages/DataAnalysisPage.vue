<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import DatasetLibrary from '../features/data-analysis/components/DatasetLibrary.vue'
import AnalysisWorkspaceView from '../features/data-analysis/components/AnalysisWorkspaceView.vue'
import SessionHub from '../features/data-analysis/components/SessionHub.vue'
import AnalysisSidebar from '../features/data-analysis/components/AnalysisSidebar.vue'
import { useAnalysisPaneLayout } from '../features/data-analysis/composables/useAnalysisPaneLayout'
import { useOpenAiAuth } from '../features/data-analysis/composables/useOpenAiAuth'
import { useDatasetLibrary } from '../features/data-analysis/composables/useDatasetLibrary'
import { useAnalysisInteractions } from '../features/data-analysis/composables/useAnalysisInteractions'
import { useAnalysisSessions } from '../features/data-analysis/composables/useAnalysisSessions'
import { shellAnalytics, shellSidebar } from '../features/data-analysis/constants/analysisPage'
import type {
  BackendConnectionStatus,
  ComposerData,
  ConversationData,
  AnalysisScreen,
  SessionItem,
  SharedAnalysisSnapshot,
} from '../features/data-analysis/types'
import { createWelcomeMessages, formatFileSize, resolveScreenFromHash } from '../features/data-analysis/utils/analysisPageHelpers'
import { getSharedAnalysisIdFromUrl, loadSharedAnalysisSnapshot, openAnalysisPreview } from '../features/data-analysis/utils/analysisShare'
import { fetchHealthcheck } from '../shared/api/portalApi'

const connectionStatus = ref<BackendConnectionStatus>('checking')
const currentScreen = ref<AnalysisScreen>(resolveScreenFromHash())
const searchQuery = ref('')
const sessionHubSearchQuery = ref('')
const datasetLibrarySearchQuery = ref('')
const isHelpDialogOpen = ref(false)
const sharedAnalysis = ref<SharedAnalysisSnapshot | null>(null)
const isCompactLayout = ref(false)
const isSidebarOpen = ref(false)
const isAnalyticsPanelOpen = ref(false)

const {
  sidebarWidth,
  isResizingSidebar,
  analyticsPaneWidth,
  isResizingAnalyticsPane,
  isAnalyticsFullscreen,
  restoreSidebarWidth,
  restoreAnalyticsPaneWidth,
  startSidebarResize,
  startAnalyticsPaneResize,
  toggleAnalyticsFullscreen,
} = useAnalysisPaneLayout()

const {
  authStatus,
  isConnecting,
  isDisconnecting,
  authError,
  bindAuthListeners,
  loadAuthStatus,
  connectOpenAi,
  logoutOpenAi,
} = useOpenAiAuth()

let removeSessionLinks: ((sessionId: string) => void) | null = null

const {
  activeSessionId,
  sessionSummaries,
  sessionStates,
  sessionHubError,
  isSessionMutating,
  ensureSessionState,
  updateSessionTitleLocally,
  syncSessionSummaryWithState,
  loadSessions,
  ensureActiveSession,
  revealSessionSummary,
  createAndSelectSession,
  selectSession,
  handleRenameSession,
  handleDeleteSession,
} = useAnalysisSessions({
  currentScreen,
  onSessionDeleted: async (sessionId) => {
    removeSessionLinks?.(sessionId)
  },
})

const activeSessionState = computed(() => {
  const sessionId = activeSessionId.value
  return sessionId ? (sessionStates.value[sessionId] ?? null) : null
})
const activeSessionSummary = computed(
  () => sessionSummaries.value.find((session) => session.id === activeSessionId.value) ?? null,
)
const activeDataset = computed(() => activeSessionState.value?.datasets[0] ?? null)

const {
  datasetsLibrary,
  selectedDatasetId,
  datasetPickerRef,
  datasetLibraryError,
  isDatasetMutating,
  isUploading,
  uploadError,
  loadDatasets,
  openDatasetPicker,
  handleDatasetFileChange,
  handleSelectDataset,
  handleAttachDataset,
  handleDetachDataset,
  handleDeleteDataset,
  removeSessionLinks: removeDatasetSessionLinks,
} = useDatasetLibrary({
  activeSessionId,
  activeSessionSummary,
  sessionStates,
  ensureActiveSession,
  ensureSessionState,
  syncSessionSummaryWithState,
})

removeSessionLinks = removeDatasetSessionLinks

const analyticsPayload = computed(() => activeSessionState.value?.analyticsPayload ?? null)
const workspacePayload = computed(() => activeSessionState.value?.workspacePayload ?? null)

const {
  interactionPickerRef,
  pendingAttachment,
  chatError,
  analyticsError,
  exportMessage,
  isSending,
  isRunningAnalysis,
  isSendingInteraction,
  canExportReport,
  openInteractionPicker,
  clearPendingAttachment,
  clearInteractionFeedback,
  queueInteractionFile,
  handleInteractionFileChange,
  handleSendMessage,
  cancelActiveChatStream,
  exportAnalyticsReport,
  shareAnalyticsReport,
} = useAnalysisInteractions({
  activeSessionState,
  activeDataset,
  analyticsPayload,
  workspacePayload,
  ensureActiveSession,
  ensureSessionState,
  updateSessionTitleLocally,
  syncSessionSummaryWithState,
  revealSessionSummary,
  loadDatasets,
  openDatasetPicker,
})

void datasetPickerRef
void interactionPickerRef

const recentSessions = computed<SessionItem[]>(() => {
  const keyword = searchQuery.value.trim().toLowerCase()
  if (!keyword) return sessionSummaries.value
  return sessionSummaries.value.filter((session) => session.title.toLowerCase().includes(keyword))
})

const conversation = computed<ConversationData>(() => ({
  messages: activeSessionState.value?.messages ?? createWelcomeMessages(),
  thinkingLabel: isSending.value
    ? isSendingInteraction.value
      ? '파일을 업로드하고 데이터를 분석하고 있어요...'
      : 'ChatGPT가 응답을 준비하고 있어요...'
    : isUploading.value
      ? '데이터셋을 업로드하고 있어요...'
      : isRunningAnalysis.value
        ? '분석을 실행하고 있어요...'
        : '다음 분석 요청을 입력해 주세요',
  isThinking: isSending.value || isUploading.value || isRunningAnalysis.value,
}))

const composer = computed<ComposerData>(() => {
  return {
    chips: [],
    placeholder: activeDataset.value
      ? `${activeDataset.value.filename} 데이터에 대해 질문하거나 다른 파일을 추가해보세요...`
      : '분석 요청을 입력하고 CSV 같은 파일을 함께 첨부해보세요...',
  }
})

const pendingAttachmentName = computed(() => {
  if (pendingAttachment.value.length === 0) return null
  if (pendingAttachment.value.length === 1) return pendingAttachment.value[0].name
  return `${pendingAttachment.value[0].name} 외 ${pendingAttachment.value.length - 1}개`
})

const pendingAttachmentMeta = computed(() => {
  if (pendingAttachment.value.length === 0) return null
  const totalSize = pendingAttachment.value.reduce((sum, file) => sum + file.size, 0)
  return `${pendingAttachment.value.length}개 파일 · ${formatFileSize(totalSize)} · 메시지와 함께 전송`
})

const sharedAnalysisCreatedAtLabel = computed(() => {
  if (!sharedAnalysis.value) return ''
  return new Intl.DateTimeFormat('ko-KR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(sharedAnalysis.value.createdAt))
})

function resetWorkspaceFeedback() {
  clearInteractionFeedback()
  uploadError.value = null
}

async function handleScreenChange(screen: AnalysisScreen) {
  currentScreen.value = screen
  if (screen === 'datasets') {
    await loadDatasets()
  }
}

function handleSessionHubSearchChange(value: string) {
  sessionHubSearchQuery.value = value
}

function handleDatasetLibrarySearchChange(value: string) {
  datasetLibrarySearchQuery.value = value
}

async function handleCreateSession() {
  resetWorkspaceFeedback()
  await createAndSelectSession()
  sessionHubSearchQuery.value = ''
  searchQuery.value = ''
  currentScreen.value = 'dashboard'
}

async function handleWorkspaceSend(message: string) {
  await handleSendMessage(message, {
    setUploadError: (message) => {
      uploadError.value = message
    },
  })
}

function handleWorkspaceDropFile(files: File[]) {
  queueInteractionFile(files, (message) => {
    uploadError.value = message
  })
}

function onInteractionFileChange(event: Event) {
  handleInteractionFileChange(event, (message) => {
    uploadError.value = message
  })
}

function openHelpDialog() {
  isHelpDialogOpen.value = true
}

function closeHelpDialog() {
  isHelpDialogOpen.value = false
}

function closeSharedAnalysisDialog() {
  sharedAnalysis.value = null
}

function syncResponsiveLayout() {
  if (typeof window === 'undefined') return

  const nextIsCompactLayout = window.innerWidth <= 960
  isCompactLayout.value = nextIsCompactLayout

  // 작은 화면에서는 패널을 접어 채팅 영역을 먼저 보여줍니다.
  if (!nextIsCompactLayout) {
    isSidebarOpen.value = false
    isAnalyticsPanelOpen.value = false
  }
}

function toggleSidebarPanel() {
  if (!isSidebarOpen.value) {
    isAnalyticsPanelOpen.value = false
  }

  isSidebarOpen.value = !isSidebarOpen.value
}

function closeSidebarPanel() {
  isSidebarOpen.value = false
}

function toggleAnalyticsPanel() {
  if (!isAnalyticsPanelOpen.value) {
    isSidebarOpen.value = false
  }

  isAnalyticsPanelOpen.value = !isAnalyticsPanelOpen.value
}

function closeAnalyticsPanel() {
  isAnalyticsPanelOpen.value = false
}

function cancelActiveRequests() {
  cancelActiveChatStream()
}

function previewSharedAnalysis() {
  if (!sharedAnalysis.value) return
  openAnalysisPreview(sharedAnalysis.value)
}

watch(activeSessionId, () => {
  exportMessage.value = null
})

watch(currentScreen, async (screen) => {
  if (isCompactLayout.value && screen !== 'dashboard') {
    isAnalyticsPanelOpen.value = false
  }

  if (screen === 'datasets' && datasetsLibrary.value.length === 0) {
    await loadDatasets()
  }
})

watch(currentScreen, (screen) => {
  window.location.hash = screen === 'dashboard' ? '#/dashboard' : screen === 'datasets' ? '#/datasets' : '#/sessions'
})

onMounted(async () => {
  const controller = new AbortController()
  syncResponsiveLayout()
  window.addEventListener('resize', syncResponsiveLayout)
  window.addEventListener('beforeunload', cancelActiveRequests)
  restoreSidebarWidth()
  restoreAnalyticsPaneWidth()
  bindAuthListeners()
  try {
    const health = await fetchHealthcheck(controller.signal)
    connectionStatus.value = health.status === 'ok' ? 'connected' : 'offline'
  } catch {
    connectionStatus.value = 'offline'
  }
  await loadAuthStatus()
  // 브라우저 새로고침은 좌측의 새로운 분석 버튼과 같은 초안 상태로 시작합니다.
  await loadSessions({ startWithDraft: true })
  await loadDatasets()

  const sharedId = getSharedAnalysisIdFromUrl()
  if (sharedId) {
    const snapshot = loadSharedAnalysisSnapshot(sharedId)
    if (snapshot) {
      sharedAnalysis.value = snapshot
      currentScreen.value = 'dashboard'
    } else {
      exportMessage.value = '공유 링크를 찾지 못했어요. 같은 브라우저에서 생성한 링크인지 확인해 주세요.'
    }
  }
})

onBeforeUnmount(() => {
  cancelActiveRequests()
  window.removeEventListener('resize', syncResponsiveLayout)
  window.removeEventListener('beforeunload', cancelActiveRequests)
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
        <button type="button" class="mobile-panel-close" @click="closeSidebarPanel">
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
        @primary-action="(screen) => { closeSidebarPanel(); void handleScreenChange(screen) }"
        @create-session="() => { closeSidebarPanel(); void handleCreateSession() }"
        @connect-open-ai="connectOpenAi"
        @disconnect-open-ai="logoutOpenAi"
        @open-help="() => { closeSidebarPanel(); openHelpDialog() }"
        @select-session="(sessionId) => { closeSidebarPanel(); void selectSession(sessionId, 'dashboard') }"
      />
    </aside>

    <button
      class="page-pane-resizer"
      :class="{ 'page-pane-resizer--active': isResizingSidebar }"
      type="button"
      aria-label="사이드바 너비 조절"
      @pointerdown="startSidebarResize"
    >
      <span></span>
    </button>

    <div class="analysis-main-shell">
      <div v-if="isCompactLayout" class="analysis-mobile-toolbar">
        <button type="button" class="analysis-mobile-toolbar__button" @click="toggleSidebarPanel">
          <span class="material-symbols-outlined">menu_open</span>
          <span>좌측 패널</span>
        </button>
        <button
          v-if="currentScreen === 'dashboard'"
          type="button"
          class="analysis-mobile-toolbar__button"
          @click="toggleAnalyticsPanel"
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
          :active-dataset="activeDataset"
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
          @drop-file="handleWorkspaceDropFile"
          @remove-attachment="clearPendingAttachment"
          @send="handleWorkspaceSend"
          @resize-start="startAnalyticsPaneResize"
          @toggle-fullscreen="toggleAnalyticsFullscreen"
          @export-report="exportAnalyticsReport"
          @share-report="shareAnalyticsReport"
          @close-analytics-panel="closeAnalyticsPanel"
        />

        <SessionHub
          v-else-if="currentScreen === 'sessions'"
          :sessions="sessionSummaries"
          :active-session-id="activeSessionId"
          :search-query="sessionHubSearchQuery"
          :is-busy="isSessionMutating"
          :error-message="sessionHubError"
          @search-change="handleSessionHubSearchChange"
          @open-session="(sessionId) => selectSession(sessionId, 'dashboard')"
          @rename-session="handleRenameSession"
          @delete-session="handleDeleteSession"
          @create-session="handleCreateSession"
        />

        <DatasetLibrary
          v-else
          :datasets="datasetsLibrary"
          :selected-dataset-id="selectedDatasetId"
          :active-session-id="activeSessionId"
          :search-query="datasetLibrarySearchQuery"
          :is-busy="isDatasetMutating"
          :error-message="datasetLibraryError"
          @search-change="handleDatasetLibrarySearchChange"
          @upload-file="openDatasetPicker"
          @select-dataset="handleSelectDataset"
          @attach-dataset="handleAttachDataset"
          @detach-dataset="handleDetachDataset"
          @delete-dataset="handleDeleteDataset"
        />
      </div>
    </div>

    <input
      ref="interactionPickerRef"
      class="dataset-picker"
      type="file"
      multiple
      accept=".csv,.tsv,.xls,.xlsx,.json,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      @change="onInteractionFileChange"
    />
    <input
      ref="datasetPickerRef"
      class="dataset-picker"
      type="file"
      accept=".csv,.tsv,.xls,.xlsx,.json,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      @change="handleDatasetFileChange"
    />

    <div v-if="isHelpDialogOpen" class="analysis-overlay" @click.self="closeHelpDialog">
      <section class="analysis-dialog">
        <header class="analysis-dialog__header">
          <div>
            <p>도움말</p>
            <h2>AI 데이터 분석 사용 안내</h2>
          </div>
          <button type="button" class="dialog-close" @click="closeHelpDialog">
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

    <div v-if="sharedAnalysis" class="analysis-overlay" @click.self="closeSharedAnalysisDialog">
      <section class="analysis-dialog analysis-dialog--wide">
        <header class="analysis-dialog__header">
          <div>
            <p>공유 미리보기</p>
            <h2>{{ sharedAnalysis.title }}</h2>
            <span class="dialog-subtext">생성 시각 {{ sharedAnalysisCreatedAtLabel }}</span>
          </div>
          <button type="button" class="dialog-close" @click="closeSharedAnalysisDialog">
            <span class="material-symbols-outlined">close</span>
          </button>
        </header>
        <pre class="shared-preview">{{ sharedAnalysis.content }}</pre>
        <div class="dialog-actions">
          <button type="button" class="dialog-button dialog-button--primary" @click="previewSharedAnalysis">새 탭 미리보기</button>
          <button type="button" class="dialog-button" @click="closeSharedAnalysisDialog">닫기</button>
        </div>
      </section>
    </div>

    <div v-if="isCompactLayout && isSidebarOpen" class="mobile-panel-backdrop" @click="closeSidebarPanel"></div>
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
