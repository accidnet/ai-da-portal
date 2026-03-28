<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import PortalDatasetLibrary from '../features/portal/components/PortalDatasetLibrary.vue'
import PortalDashboardWorkspaceView from '../features/portal/components/PortalDashboardWorkspaceView.vue'
import PortalSessionHub from '../features/portal/components/PortalSessionHub.vue'
import PortalSidebar from '../features/portal/components/PortalSidebar.vue'
import { usePortalAnalyticsPane } from '../features/portal/composables/usePortalAnalyticsPane'
import { usePortalAuth } from '../features/portal/composables/usePortalAuth'
import { usePortalDatasets } from '../features/portal/composables/usePortalDatasets'
import { usePortalInteractions } from '../features/portal/composables/usePortalInteractions'
import { usePortalSessions } from '../features/portal/composables/usePortalSessions'
import { shellAnalytics, shellSidebar } from '../features/portal/constants/portalPage'
import type {
  BackendConnectionStatus,
  ComposerChip,
  ComposerData,
  ConversationData,
  PortalScreen,
  SessionItem,
  SharedAnalysisSnapshot,
} from '../features/portal/types'
import { createWelcomeMessages, formatFileSize, resolveScreenFromHash } from '../features/portal/utils/portalPageHelpers'
import { getSharedAnalysisIdFromUrl, loadSharedAnalysisSnapshot, openAnalysisPreview } from '../features/portal/utils/portalShare'
import { fetchHealthcheck } from '../shared/api/portalApi'

const connectionStatus = ref<BackendConnectionStatus>('checking')
const currentScreen = ref<PortalScreen>(resolveScreenFromHash())
const searchQuery = ref('')
const sessionHubSearchQuery = ref('')
const datasetLibrarySearchQuery = ref('')
const isHelpDialogOpen = ref(false)
const sharedAnalysis = ref<SharedAnalysisSnapshot | null>(null)

const {
  analyticsPaneWidth,
  isResizingAnalyticsPane,
  isAnalyticsFullscreen,
  restoreAnalyticsPaneWidth,
  startAnalyticsPaneResize,
  toggleAnalyticsFullscreen,
} = usePortalAnalyticsPane()

const { authStatus, isConnecting, authError, bindAuthListeners, loadAuthStatus, connectOpenAi } = usePortalAuth()

let removeSessionLinks: ((sessionId: string) => void) | null = null

const {
  activeSessionId,
  sessionSummaries,
  sessionStates,
  sessionHubError,
  isSessionMutating,
  ensureSessionState,
  syncSessionSummaryWithState,
  loadSessions,
  ensureActiveSession,
  createAndSelectSession,
  selectSession,
  handleRenameSession,
  handleDeleteSession,
} = usePortalSessions({
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
} = usePortalDatasets({
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
  handleSuggestedPrompt,
  exportAnalyticsReport,
  shareAnalyticsReport,
} = usePortalInteractions({
  activeSessionState,
  activeDataset,
  analyticsPayload,
  workspacePayload,
  ensureActiveSession,
  ensureSessionState,
  syncSessionSummaryWithState,
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
  const chips: ComposerChip[] = []
  chips.push({
    icon: authStatus.value.connected ? 'smart_toy' : 'analytics',
    label: authStatus.value.connected ? 'ChatGPT 연결됨' : '백엔드 분석 모드',
    tone: authStatus.value.connected ? 'primary' : 'neutral',
  })
  if (activeSessionState.value?.title) {
    chips.push({
      icon: 'forum',
      label: activeSessionState.value.title,
      tone: 'neutral',
    })
  }
  if (activeDataset.value) {
    chips.push({
      icon: 'database',
      label: `${activeDataset.value.filename} · 활성`,
      tone: 'primary',
    })
  }
  const extraDatasetCount = Math.max((activeSessionState.value?.datasets.length ?? 0) - 1, 0)
  if (extraDatasetCount > 0) {
    chips.push({
      icon: 'dataset',
      label: `추가 ${extraDatasetCount}개`,
      tone: 'neutral',
    })
  }
  if (isUploading.value) {
    chips.push({
      icon: 'progress_activity',
      label: '업로드 중',
      tone: 'neutral',
    })
  }
  return {
    chips,
    placeholder: activeDataset.value
      ? `${activeDataset.value.filename} 데이터에 대해 질문하거나 다른 파일을 추가해보세요...`
      : '분석 요청을 입력하고 CSV 같은 파일을 함께 첨부해보세요...',
  }
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

async function handleScreenChange(screen: PortalScreen) {
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

function handleWorkspaceDropFile(file: File) {
  queueInteractionFile(file, (message) => {
    uploadError.value = message
  })
}

function onInteractionFileChange(event: Event) {
  handleInteractionFileChange(event, (message) => {
    uploadError.value = message
  })
}

async function onSuggestedPrompt(prompt: string) {
  if (isUploading.value) return
  await handleSuggestedPrompt(prompt, (message) => {
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

function previewSharedAnalysis() {
  if (!sharedAnalysis.value) return
  openAnalysisPreview(sharedAnalysis.value)
}

watch(activeSessionId, () => {
  exportMessage.value = null
})

watch(currentScreen, async (screen) => {
  if (screen === 'datasets' && datasetsLibrary.value.length === 0) {
    await loadDatasets()
  }
})

watch(currentScreen, (screen) => {
  window.location.hash = screen === 'dashboard' ? '#/dashboard' : screen === 'datasets' ? '#/datasets' : '#/sessions'
})

onMounted(async () => {
  const controller = new AbortController()
  restoreAnalyticsPaneWidth()
  bindAuthListeners()
  try {
    const health = await fetchHealthcheck(controller.signal)
    connectionStatus.value = health.status === 'ok' ? 'connected' : 'offline'
  } catch {
    connectionStatus.value = 'offline'
  }
  await loadAuthStatus()
  await loadSessions()
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
</script>

<template>
  <div class="portal-layout">
    <PortalSidebar
      :sidebar="{ ...shellSidebar, recentSessions }"
      :active-screen="currentScreen"
      :active-session-id="activeSessionId"
      :connection-status="connectionStatus"
      :auth-status="authStatus"
      :is-connecting="isConnecting"
      @primary-action="handleScreenChange"
      @create-session="handleCreateSession"
      @connect-open-ai="connectOpenAi"
      @open-help="openHelpDialog"
      @select-session="(sessionId) => selectSession(sessionId, 'dashboard')"
    />

    <div class="portal-main-shell">
      <div v-if="authError || exportMessage" class="portal-status-messages">
        <p v-if="authError" class="auth-error">{{ authError }}</p>
        <p v-if="exportMessage" class="export-message">{{ exportMessage }}</p>
      </div>

      <div class="portal-screen-shell">
        <PortalDashboardWorkspaceView
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
          :can-export-report="canExportReport"
          :pending-attachment-name="pendingAttachment?.name ?? null"
          :pending-attachment-meta="pendingAttachment ? `${formatFileSize(pendingAttachment.size)} · 메시지와 함께 전송` : null"
          @attach="openInteractionPicker"
          @drop-file="handleWorkspaceDropFile"
          @remove-attachment="clearPendingAttachment"
          @send="handleWorkspaceSend"
          @resize-start="startAnalyticsPaneResize"
          @prompt-click="onSuggestedPrompt"
          @toggle-fullscreen="toggleAnalyticsFullscreen"
          @export-report="exportAnalyticsReport"
          @share-report="shareAnalyticsReport"
        />

        <PortalSessionHub
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

        <PortalDatasetLibrary
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

    <div v-if="isHelpDialogOpen" class="portal-overlay" @click.self="closeHelpDialog">
      <section class="portal-dialog">
        <header class="portal-dialog__header">
          <div>
            <p>도움말</p>
            <h2>데이터 분석 AI 사용 안내</h2>
          </div>
          <button type="button" class="dialog-close" @click="closeHelpDialog">
            <span class="material-symbols-outlined">close</span>
          </button>
        </header>
        <ul class="help-list">
          <li>좌측의 <strong>새로운 분석</strong>을 누르면 새 세션이 생성됩니다.</li>
          <li>데이터 소스 화면에서 파일 업로드 후 활성 세션에 바로 연결할 수 있습니다.</li>
          <li>오른쪽 작업공간의 <strong>공유</strong>는 현재 브라우저 기반 링크 복사, <strong>미리보기</strong>는 새 탭 리포트 열기입니다.</li>
          <li>ChatGPT 연결은 좌측 하단에서 바로 진행할 수 있습니다.</li>
        </ul>
      </section>
    </div>

    <div v-if="sharedAnalysis" class="portal-overlay" @click.self="closeSharedAnalysisDialog">
      <section class="portal-dialog portal-dialog--wide">
        <header class="portal-dialog__header">
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
  </div>
</template>

<style scoped>
.portal-layout {
  position: relative;
  height: 100vh;
  display: grid;
  grid-template-columns: 288px minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr);
  gap: 24px;
  padding: 24px;
  overflow: hidden;
}

.portal-main-shell {
  min-width: 0;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
}

.portal-status-messages {
  display: grid;
  gap: 8px;
}

.portal-screen-shell {
  min-height: 0;
  height: 100%;
  flex: 1;
  display: grid;
  gap: 18px;
  overflow: hidden;
}

.auth-error,
.export-message {
  margin: -8px 4px 0;
  font-size: 0.86rem;
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

.portal-overlay {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.34);
}

.portal-dialog {
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

.portal-dialog--wide {
  width: min(880px, 100%);
}

.portal-dialog__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.portal-dialog__header p,
.help-list,
.dialog-subtext {
  margin: 0;
  color: var(--color-text-muted);
}

.portal-dialog__header p {
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.7rem;
  font-weight: 800;
}

.portal-dialog__header h2 {
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
  .portal-layout {
    grid-template-columns: 248px minmax(0, 1fr);
  }
}

@media (max-width: 960px) {
  .portal-layout {
    grid-template-columns: minmax(0, 1fr);
    padding: 16px;
    height: auto;
    min-height: 100vh;
    overflow: auto;
  }

  .portal-main-shell,
  .portal-screen-shell {
    overflow: visible;
  }

  .portal-overlay {
    padding: 16px;
  }
}
</style>
