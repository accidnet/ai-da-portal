<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import PortalLayout from '@/layouts/portal/PortalLayout.vue'
import { useAnalysisPaneLayout } from '@/features/data-analysis/composables/useAnalysisPaneLayout'
import { useOpenAiAuth } from '@/features/data-analysis/composables/useOpenAiAuth'
import { useDatasetLibrary } from '@/features/data-analysis/composables/useDatasetLibrary'
import { useAnalysisInteractions } from '@/features/data-analysis/composables/useAnalysisInteractions'
import { useAnalysisSessions } from '@/features/data-analysis/composables/useAnalysisSessions'
import { shellAnalytics, shellSidebar } from '@/features/data-analysis/constants/analysisPage'
import type {
  BackendConnectionStatus,
  ComposerData,
  ConversationData,
  AnalysisScreen,
  SessionItem,
  SharedAnalysisSnapshot,
} from '@/features/data-analysis/types'
import { createWelcomeMessages, formatFileSize, resolveScreenFromHash } from '@/features/data-analysis/utils/analysisPageHelpers'
import { getSharedAnalysisIdFromUrl, loadSharedAnalysisSnapshot, openAnalysisPreview } from '@/features/data-analysis/utils/analysisShare'
import { fetchHealthcheck } from '@/shared/api/portalApi'

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
const portalLayoutRef = ref<InstanceType<typeof PortalLayout> | null>(null)

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
  datasetLibraryError,
  isDatasetMutating,
  isUploading,
  uploadError,
  loadDatasets,
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
  pendingAttachment,
  chatError,
  analyticsError,
  exportMessage,
  isSending,
  isRunningAnalysis,
  isSendingInteraction,
  canExportReport,
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
  openDatasetPicker: () => portalLayoutRef.value?.openDatasetPicker(),
})

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
      : '데이터를 분석하고 있어요...'
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
  // 브라우저 새로고침 후에도 마지막으로 작업하던 분석 세션을 복원합니다.
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

onBeforeUnmount(() => {
  cancelActiveRequests()
  window.removeEventListener('resize', syncResponsiveLayout)
  window.removeEventListener('beforeunload', cancelActiveRequests)
})
</script>

<template>
  <PortalLayout
    ref="portalLayoutRef"
    :sidebar-width="sidebarWidth"
    :is-resizing-sidebar="isResizingSidebar"
    :analytics-pane-width="analyticsPaneWidth"
    :is-resizing-analytics-pane="isResizingAnalyticsPane"
    :is-analytics-fullscreen="isAnalyticsFullscreen"
    :is-compact-layout="isCompactLayout"
    :is-sidebar-open="isSidebarOpen"
    :is-analytics-panel-open="isAnalyticsPanelOpen"
    :shell-sidebar="shellSidebar"
    :shell-analytics="shellAnalytics"
    :recent-sessions="recentSessions"
    :current-screen="currentScreen"
    :active-session-id="activeSessionId"
    :connection-status="connectionStatus"
    :auth-status="authStatus"
    :is-connecting="isConnecting"
    :is-disconnecting="isDisconnecting"
    :auth-error="authError"
    :export-message="exportMessage"
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
    :session-summaries="sessionSummaries"
    :session-hub-search-query="sessionHubSearchQuery"
    :session-hub-error="sessionHubError"
    :is-session-mutating="isSessionMutating"
    :datasets-library="datasetsLibrary"
    :selected-dataset-id="selectedDatasetId"
    :dataset-library-search-query="datasetLibrarySearchQuery"
    :dataset-library-error="datasetLibraryError"
    :is-dataset-mutating="isDatasetMutating"
    :is-help-dialog-open="isHelpDialogOpen"
    :shared-analysis="sharedAnalysis"
    :shared-analysis-created-at-label="sharedAnalysisCreatedAtLabel"
    @primary-action="(screen) => { closeSidebarPanel(); void handleScreenChange(screen) }"
    @create-session="() => { closeSidebarPanel(); void handleCreateSession() }"
    @connect-open-ai="connectOpenAi"
    @disconnect-open-ai="logoutOpenAi"
    @open-help="() => { closeSidebarPanel(); openHelpDialog() }"
    @select-session="(sessionId) => { closeSidebarPanel(); void selectSession(sessionId, 'dashboard') }"
    @delete-session="(sessionId) => { void handleDeleteSession(sessionId) }"
    @sidebar-resize-start="startSidebarResize"
    @toggle-sidebar-panel="toggleSidebarPanel"
    @toggle-analytics-panel="toggleAnalyticsPanel"
    @session-hub-search-change="handleSessionHubSearchChange"
    @open-session="(sessionId) => selectSession(sessionId, 'dashboard')"
    @rename-session="handleRenameSession"
    @dataset-library-search-change="handleDatasetLibrarySearchChange"
    @select-dataset="handleSelectDataset"
    @attach-dataset="handleAttachDataset"
    @detach-dataset="handleDetachDataset"
    @delete-dataset="handleDeleteDataset"
    @interaction-file-change="onInteractionFileChange"
    @dataset-file-change="handleDatasetFileChange"
    @drop-file="handleWorkspaceDropFile"
    @remove-attachment="clearPendingAttachment"
    @send="handleWorkspaceSend"
    @analytics-resize-start="startAnalyticsPaneResize"
    @toggle-fullscreen="toggleAnalyticsFullscreen"
    @export-report="exportAnalyticsReport"
    @share-report="shareAnalyticsReport"
    @close-analytics-panel="closeAnalyticsPanel"
    @close-sidebar-panel="closeSidebarPanel"
    @close-help-dialog="closeHelpDialog"
    @close-shared-analysis-dialog="closeSharedAnalysisDialog"
    @preview-shared-analysis="previewSharedAnalysis"
  />
</template>
