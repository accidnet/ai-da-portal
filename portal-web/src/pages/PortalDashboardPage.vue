<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import PortalAnalyticsPane from '../features/portal/components/PortalAnalyticsPane.vue'
import PortalConversationPane from '../features/portal/components/PortalConversationPane.vue'
import PortalHeader from '../features/portal/components/PortalHeader.vue'
import PortalSidebar from '../features/portal/components/PortalSidebar.vue'
import type {
  AnalyticsData,
  AnalyticsPayload,
  ChatMessage,
  ComposerChip,
  ComposerData,
  ConversationData,
  DatasetAsset,
  HeaderData,
  MessageAttachmentPreview,
  OpenAiAuthStatus,
  SessionItem,
  SidebarData,
  WorkspacePayload,
} from '../features/portal/types'
import {
  authorizeOpenAi,
  type ChatInteractionResponse,
  createAnalysis,
  createSession,
  fetchDatasetPreview,
  fetchDatasetProfile,
  fetchHealthcheck,
  fetchOpenAiAuthStatus,
  fetchSessions,
  sendChatInteraction,
  sendChatMessage,
  uploadDataset,
} from '../shared/api/portalApi'

interface SessionRuntimeState {
  title: string
  messages: ChatMessage[]
  analyticsPayload: AnalyticsPayload | null
  workspacePayload: WorkspacePayload | null
  datasets: DatasetAsset[]
}

interface OpenAiPopupMessage {
  source?: string
  status?: 'success' | 'error'
  error?: string
  account_email?: string
}

const OPENAI_AUTH_POPUP_SOURCE = 'portal-openai-auth'
const ANALYTICS_PANE_WIDTH_STORAGE_KEY = 'portal.analyticsPaneWidth'

const shellSidebar: SidebarData = {
  productName: 'Data Analysis AI',
  productTagline: 'Data Intelligence',
  primaryNav: [
    { label: 'New Analysis', icon: 'add_chart', active: true },
    { label: 'History', icon: 'history' },
    { label: 'Data Sources', icon: 'database' },
    { label: 'Models', icon: 'neurology' },
  ],
  recentSessions: [],
  secondaryNav: [
    { label: 'Settings', icon: 'settings' },
    { label: 'Help', icon: 'help' },
  ],
  profile: {
    name: 'Alex Architect',
    plan: 'Pro Plan',
    initials: 'AA',
  },
}

const shellHeader: HeaderData = {
  searchPlaceholder: 'Search analysis, datasets, or prompts...',
  actions: ['notifications', 'ios_share', 'account_circle'],
}

const shellAnalytics: AnalyticsData = {
  title: 'Analytical Canvas',
  chartTitle: 'Waiting for live analysis',
  chartChange: 'No analysis yet',
  chartPoints: [],
  metrics: [],
  tableRows: [],
  insight: {
    title: 'Start here',
    body: 'Upload a dataset or send a prompt to populate the analytics pane with live backend output.',
    actionLabel: 'Run Analysis',
  },
}

const connectionStatus = ref<'checking' | 'connected' | 'offline'>('checking')
const authStatus = ref<OpenAiAuthStatus>({
  state: 'disconnected',
  connected: false,
  pending: false,
  accountEmail: null,
  accountId: null,
  expiresAt: null,
  scopes: [],
})
const isConnecting = ref(false)
const authError = ref<string | null>(null)
const chatError = ref<string | null>(null)
const uploadError = ref<string | null>(null)
const analyticsError = ref<string | null>(null)
const isSending = ref(false)
const isUploading = ref(false)
const isRunningAnalysis = ref(false)
const isSendingInteraction = ref(false)
const searchQuery = ref('')
const analyticsPaneWidth = ref(420)
const isResizingAnalyticsPane = ref(false)
const activeSessionId = ref<string | null>(null)
const sessionSummaries = ref<SessionItem[]>([])
const sessionStates = ref<Record<string, SessionRuntimeState>>({})
const datasetPickerRef = ref<HTMLInputElement | null>(null)
const interactionPickerRef = ref<HTMLInputElement | null>(null)
const pendingAttachment = ref<File | null>(null)
let authPollTimer: number | null = null
let authPopup: Window | null = null

function clampAnalyticsPaneWidth(width: number): number {
  return Math.min(Math.max(width, 320), 720)
}

function handleAnalyticsPaneResize(event: PointerEvent) {
  if (!isResizingAnalyticsPane.value || window.innerWidth <= 1280) {
    return
  }

  analyticsPaneWidth.value = clampAnalyticsPaneWidth(window.innerWidth - event.clientX - 48)
}

function stopAnalyticsPaneResize() {
  isResizingAnalyticsPane.value = false
  window.removeEventListener('pointermove', handleAnalyticsPaneResize)
  window.removeEventListener('pointerup', stopAnalyticsPaneResize)
}

function startAnalyticsPaneResize(event: PointerEvent) {
  if (window.innerWidth <= 1280) {
    return
  }

  event.preventDefault()
  isResizingAnalyticsPane.value = true
  window.addEventListener('pointermove', handleAnalyticsPaneResize)
  window.addEventListener('pointerup', stopAnalyticsPaneResize)
}

function restoreAnalyticsPaneWidth() {
  const storedWidth = window.localStorage.getItem(ANALYTICS_PANE_WIDTH_STORAGE_KEY)
  if (!storedWidth) {
    return
  }

  const parsedWidth = Number(storedWidth)
  if (!Number.isFinite(parsedWidth)) {
    return
  }

  analyticsPaneWidth.value = clampAnalyticsPaneWidth(parsedWidth)
}

function createWelcomeMessages(title: string): ChatMessage[] {
  return [
    {
      role: 'assistant',
      author: 'AI 데이터 분석가',
      text: `${title} 세션입니다. 데이터셋을 업로드하거나 프롬프트를 보내면 바로 분석을 시작할 수 있어요.`,
      bullets: [
        { text: 'CSV 또는 스프레드시트 파일 업로드하기' },
        { text: '추세, 상관관계, 이상치 분석 요청하기' },
        { text: '대시보드 카드용 요약 분석 실행하기' },
      ],
    },
  ]
}

function normalizeAssistantMessage(message: string, followUpSuggestions: string[]): string {
  const suggestions = followUpSuggestions.map((item) => item.trim()).filter(Boolean)
  let normalizedMessage = message.trim()

  normalizedMessage = normalizedMessage.replace(/^\[(?:Pasted?|Past)\s*/i, '')

  for (const suggestion of suggestions) {
    const escapedSuggestion = suggestion.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    normalizedMessage = normalizedMessage.replace(new RegExp(`(?:^|\\s|[-*]\\s*)${escapedSuggestion}`, 'g'), ' ')
  }

  return normalizedMessage
    .split(/\r?\n/)
    .map((line) => line.replace(/^[-*]\s+/, '').trim())
    .filter(Boolean)
    .join('\n')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

function createSessionState(title: string): SessionRuntimeState {
  return {
    title,
    messages: createWelcomeMessages(title),
    analyticsPayload: null,
    workspacePayload: null,
    datasets: [],
  }
}

function ensureSessionState(sessionId: string, title: string): SessionRuntimeState {
  const existing = sessionStates.value[sessionId]
  if (existing) {
    existing.title = title
    return existing
  }

  const created = createSessionState(title)
  sessionStates.value[sessionId] = created
  return created
}

function updateSessionSummary(sessionId: string, title: string) {
  const current = sessionSummaries.value.filter((session) => session.id !== sessionId)
  sessionSummaries.value = [
    { id: sessionId, title },
    ...current,
  ]
}

function buildSessionTitle(): string {
  return `Analysis Session ${sessionSummaries.value.length + 1}`
}

function syncAuthPolling() {
  if (authStatus.value.connected || (!authStatus.value.pending && !isConnecting.value)) {
    if (authPollTimer !== null) {
      window.clearInterval(authPollTimer)
      authPollTimer = null
    }
    return
  }

  if (authPollTimer === null) {
    authPollTimer = window.setInterval(async () => {
      await loadAuthStatus()
    }, 3000)
  }
}

async function loadAuthStatus() {
  try {
    const status = await fetchOpenAiAuthStatus()
    authStatus.value = {
      state: status.state,
      connected: status.connected,
      pending: status.pending,
      accountEmail: status.account_email,
      accountId: status.account_id,
      expiresAt: status.expires_at,
      scopes: status.scopes,
    }
    isConnecting.value = status.pending
    if (status.connected) {
      authError.value = null
      authPopup = null
    } else if (!status.pending) {
      authPopup = null
    }
  } catch {
    authError.value = 'ChatGPT connection status could not be loaded.'
  } finally {
    syncAuthPolling()
  }
}

async function handleOpenAiAuthMessage(event: MessageEvent<OpenAiPopupMessage>) {
  if (!authPopup || event.source !== authPopup) {
    return
  }

  if (event.data?.source !== OPENAI_AUTH_POPUP_SOURCE) {
    return
  }

  authPopup = null

  if (event.data.status === 'error') {
    isConnecting.value = false
    authError.value = event.data.error ?? 'ChatGPT sign-in did not complete.'
    await loadAuthStatus()
    return
  }

  authError.value = null
  await loadAuthStatus()
}

function handleWindowFocus() {
  if (authStatus.value.pending || isConnecting.value) {
    void loadAuthStatus()
  }
}

function buildPopupFeatures() {
  const width = 560
  const height = 720
  const left = Math.max(window.screenX + Math.round((window.outerWidth - width) / 2), 0)
  const top = Math.max(window.screenY + Math.round((window.outerHeight - height) / 2), 0)

  return `popup=yes,width=${width},height=${height},left=${left},top=${top}`
}

async function loadSessions() {
  try {
    const sessions = await fetchSessions()
    sessionSummaries.value = sessions.map((session) => ({
      id: session.id,
      title: session.title,
    }))

    if (sessionSummaries.value.length === 0) {
      const created = await createSession('ChatGPT analysis session')
      sessionSummaries.value = [{ id: created.id, title: created.title }]
      activeSessionId.value = created.id
      ensureSessionState(created.id, created.title)
      return
    }

    for (const session of sessionSummaries.value) {
      if (!session.id) {
        continue
      }

      ensureSessionState(session.id, session.title)
    }

    const firstSessionId = sessionSummaries.value[0]?.id
    if (!activeSessionId.value || !sessionStates.value[activeSessionId.value]) {
      activeSessionId.value = firstSessionId ?? null
    }
  } catch {
    if (!activeSessionId.value) {
      const fallback = 'local-session'
      activeSessionId.value = fallback
      sessionSummaries.value = [{ id: fallback, title: 'ChatGPT analysis session' }]
      ensureSessionState(fallback, 'ChatGPT analysis session')
    }
  }
}

function getActiveSessionId(): string {
  if (activeSessionId.value) {
    return activeSessionId.value
  }

  const fallback = 'local-session'
  activeSessionId.value = fallback
  ensureSessionState(fallback, 'ChatGPT analysis session')
  updateSessionSummary(fallback, 'ChatGPT analysis session')
  return fallback
}

async function ensureActiveSession() {
  const currentSessionId = getActiveSessionId()
  const state = sessionStates.value[currentSessionId]
  if (state) {
    return currentSessionId
  }

  const created = await createSession('ChatGPT analysis session')
  activeSessionId.value = created.id
  sessionSummaries.value = [{ id: created.id, title: created.title }, ...sessionSummaries.value]
  ensureSessionState(created.id, created.title)
  return created.id
}

async function createAndSelectSession() {
  chatError.value = null
  uploadError.value = null
  analyticsError.value = null

  try {
    const created = await createSession(buildSessionTitle())
    activeSessionId.value = created.id
    ensureSessionState(created.id, created.title)
    updateSessionSummary(created.id, created.title)
    searchQuery.value = ''
  } catch {
    chatError.value = '새 분석 세션을 만들지 못했어요. 잠시 후 다시 시도해 주세요.'
  }
}

async function connectOpenAi() {
  if (authPopup && !authPopup.closed) {
    authPopup.focus()
    return
  }

  isConnecting.value = true
  authError.value = null

  try {
    const authorization = await authorizeOpenAi()
    const popup = window.open(
      authorization.authorization_url,
      'portal-openai-auth',
      buildPopupFeatures(),
    )

    if (!popup) {
      window.location.assign(authorization.authorization_url)
      return
    }

    authPopup = popup

    authStatus.value = {
      ...authStatus.value,
      state: 'pending',
      pending: true,
      connected: false,
    }
  } catch {
    isConnecting.value = false
    authError.value = 'ChatGPT sign-in could not be started.'
  } finally {
    syncAuthPolling()
  }
}

function selectSession(sessionId: string) {
  activeSessionId.value = sessionId
  const summary = sessionSummaries.value.find((session) => session.id === sessionId)
  ensureSessionState(sessionId, summary?.title ?? 'ChatGPT analysis session')
}

function handlePrimaryAction(label: string) {
  if (label === 'New Analysis') {
    void createAndSelectSession()
  }
}

function handleSearchChange(value: string) {
  searchQuery.value = value
}

async function handleSendMessage(message: string) {
  chatError.value = null
  uploadError.value = null
  analyticsError.value = null

  const sessionId = await ensureActiveSession()
  const sessionState = ensureSessionState(sessionId, 'ChatGPT analysis session')
  const attachedFile = pendingAttachment.value
  const userMessage = message || (attachedFile ? `${attachedFile.name} 파일을 업로드해서 분석해줘.` : '')
  const userMessageEntry: ChatMessage = {
    role: 'user',
    text: userMessage,
    attachmentPreview: attachedFile
      ? {
        filename: attachedFile.name,
        meta: `${formatFileSize(attachedFile.size)} · 업로드 중`,
        columns: [],
        rows: [],
      }
      : undefined,
  }

  sessionState.messages = [
    ...sessionState.messages,
    userMessageEntry,
  ]
  isSending.value = true
  isSendingInteraction.value = Boolean(attachedFile)
  pendingAttachment.value = null

  try {
    const response = attachedFile
      ? await sendChatInteraction({
        sessionId,
        message: userMessage,
        datasetIds: sessionState.datasets.map((dataset) => dataset.id),
        file: attachedFile,
      })
      : await sendChatMessage({
        sessionId,
        message: userMessage,
        datasetIds: sessionState.datasets.map((dataset) => dataset.id),
      })

    const interactionResponse = attachedFile ? response as ChatInteractionResponse : null

    if (interactionResponse?.dataset) {
      const interactionDataset = interactionResponse.dataset
      const dataset = createDatasetAsset(
        interactionDataset.detail,
        interactionDataset.preview,
        interactionDataset.profile,
      )
      sessionState.datasets = [dataset, ...sessionState.datasets.filter((item) => item.id !== dataset.id)]
      sessionState.messages = sessionState.messages.map((entry) => (
        entry === userMessageEntry
          ? {
            ...entry,
            attachmentPreview: createAttachmentPreview(
              interactionDataset.detail.filename,
              attachedFile?.size ?? 0,
              interactionDataset.preview,
            ),
          }
          : entry
      ))
    }

    sessionState.messages = [
      ...sessionState.messages,
      {
        role: 'assistant',
        author: 'AI 데이터 분석가',
        text: normalizeAssistantMessage(response.assistant_message, response.follow_up_suggestions),
        bullets: response.follow_up_suggestions.map((text) => ({ text })),
      },
    ]
    sessionState.analyticsPayload = response.analytics
    sessionState.workspacePayload = response.workspace
    updateSessionSummary(sessionId, sessionState.title)
  } catch (error) {
    chatError.value = error instanceof Error
      ? error.message
      : 'The message could not be sent. Check ChatGPT connection and backend status.'
    pendingAttachment.value = attachedFile
  } finally {
    isSending.value = false
    isSendingInteraction.value = false
  }
}

function openDatasetPicker() {
  datasetPickerRef.value?.click()
}

function openInteractionPicker() {
  interactionPickerRef.value?.click()
}

function clearPendingAttachment() {
  pendingAttachment.value = null
}

function formatFileSize(size: number): string {
  if (size < 1024) {
    return `${size} B`
  }

  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`
  }

  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function createAttachmentPreview(
  filename: string,
  size: number,
  preview: {
    columns: string[]
    rows: Array<Record<string, string | number | null>>
  },
): MessageAttachmentPreview {
  return {
    filename,
    meta: `${formatFileSize(size)} · ${preview.rows.length} rows preview`,
    columns: preview.columns,
    rows: preview.rows,
  }
}

function queueInteractionFile(file: File) {
  if (!file.name.toLowerCase().endsWith('.csv') && !file.type.includes('csv') && !file.type.startsWith('text/') && !file.name.toLowerCase().endsWith('.tsv') && !file.name.toLowerCase().endsWith('.xls') && !file.name.toLowerCase().endsWith('.xlsx') && !file.name.toLowerCase().endsWith('.json')) {
    uploadError.value = 'CSV 또는 스프레드시트 파일만 업로드할 수 있어요.'
    return
  }

  uploadError.value = null
  pendingAttachment.value = file
}

function handleInteractionFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''

  if (!file) {
    return
  }

  queueInteractionFile(file)
}

function mapDatasetProfile(payload: {
  row_count: number
  column_count: number
  columns: Array<{
    name: string
    dtype: string
    null_ratio: number
    sample_values: string[]
  }>
  suggested_prompts: string[]
}): DatasetAsset['profile'] {
  return {
    rowCount: payload.row_count,
    columnCount: payload.column_count,
    columns: payload.columns.map((column) => ({
      name: column.name,
      dtype: column.dtype,
      nullRatio: column.null_ratio,
      sampleValues: column.sample_values,
    })),
    suggestedPrompts: payload.suggested_prompts,
  }
}

function createDatasetAsset(
  detail: {
    id: string
    filename: string
    content_type: string | null
    created_at: string
  },
  preview: {
    columns: string[]
    rows: Array<Record<string, string | number | null>>
  },
  profile: {
    profile: {
      row_count: number
      column_count: number
      columns: Array<{
        name: string
        dtype: string
        null_ratio: number
        sample_values: string[]
      }>
      suggested_prompts: string[]
    }
  },
): DatasetAsset {
  return {
    id: detail.id,
    filename: detail.filename,
    contentType: detail.content_type,
    createdAt: detail.created_at,
    preview: {
      columns: preview.columns,
      rows: preview.rows,
    },
    profile: mapDatasetProfile(profile.profile),
  }
}

async function handleDatasetFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''

  if (!file) {
    return
  }

  await processDatasetFile(file)
}

async function processDatasetFile(file: File) {
  if (!file.name.toLowerCase().endsWith('.csv') && !file.type.includes('csv') && !file.type.startsWith('text/') && !file.name.toLowerCase().endsWith('.tsv') && !file.name.toLowerCase().endsWith('.xls') && !file.name.toLowerCase().endsWith('.xlsx') && !file.name.toLowerCase().endsWith('.json')) {
    uploadError.value = 'CSV 또는 스프레드시트 파일만 업로드할 수 있어요.'
    return
  }

  analyticsError.value = null
  uploadError.value = null
  isUploading.value = true

  try {
    const sessionId = await ensureActiveSession()
    const detail = await uploadDataset(file)
    const [preview, profile] = await Promise.all([
      fetchDatasetPreview(detail.id),
      fetchDatasetProfile(detail.id),
    ])

    const dataset = createDatasetAsset(detail, preview, profile)

    const sessionState = ensureSessionState(sessionId, 'ChatGPT analysis session')
    sessionState.datasets = [dataset, ...sessionState.datasets.filter((item) => item.id !== dataset.id)]
    sessionState.analyticsPayload = null
    sessionState.workspacePayload = null
    sessionState.messages = [
      ...sessionState.messages,
      {
        role: 'assistant',
        author: 'AI 데이터 분석가',
        text: `${dataset.filename} 업로드를 완료했어요. 이제 같은 데이터셋 ID로 채팅과 분석을 이어서 실행할 수 있어요.`,
        bullets: [
          {
            text: `${dataset.profile?.rowCount ?? 0} rows / ${dataset.profile?.columnCount ?? 0} columns profiled`,
          },
          { text: '우측 패널에 서버 기준 미리보기와 프로파일이 반영됨' },
          { text: '이제 프롬프트 전송과 Run Analysis가 동일한 데이터셋을 사용함' },
        ],
      },
    ]
    updateSessionSummary(sessionId, sessionState.title)
    activeSessionId.value = sessionId
  } catch {
    uploadError.value = 'Dataset upload failed. Please try again with a CSV or spreadsheet file.'
  } finally {
    isUploading.value = false
  }
}

async function runAnalysis() {
  analyticsError.value = null
  const sessionId = await ensureActiveSession()
  const sessionState = ensureSessionState(sessionId, 'ChatGPT analysis session')
  const primaryDataset = sessionState.datasets[0]

  if (!primaryDataset) {
    analyticsError.value = 'Upload a dataset first to run analysis.'
    return
  }

  isRunningAnalysis.value = true

  try {
    const analysis = await createAnalysis({
      sessionId,
      datasetId: primaryDataset.id,
      analysisType: 'dataset_profile',
      prompt: `Generate a dashboard-ready profile for ${primaryDataset.filename}.`,
    })

    sessionState.analyticsPayload = analysis.analytics
    sessionState.workspacePayload = analysis.workspace
    sessionState.messages = [
      ...sessionState.messages,
      {
        role: 'assistant',
        author: 'AI 데이터 분석가',
        text:
          analysis.analytics?.insights[0]?.body ??
          'Analysis completed. The live analytics panel has been refreshed.',
      },
    ]
    updateSessionSummary(sessionId, sessionState.title)
  } catch {
    analyticsError.value = 'Analysis could not be started.'
  } finally {
    isRunningAnalysis.value = false
  }
}

async function handleSuggestedPrompt(prompt: string) {
  if (!prompt || isSending.value || isUploading.value || isRunningAnalysis.value) {
    return
  }

  await handleSendMessage(prompt)
}

async function handleInsightAction() {
  if (isSending.value || isUploading.value || isRunningAnalysis.value) {
    return
  }

  if (activeDataset.value) {
    await runAnalysis()
    return
  }

  openDatasetPicker()
}

const activeSessionState = computed(() => {
  const sessionId = activeSessionId.value
  if (!sessionId) {
    return null
  }
  return sessionStates.value[sessionId] ?? null
})

const activeDataset = computed(() => activeSessionState.value?.datasets[0] ?? null)

const recentSessions = computed<SessionItem[]>(() => {
  const keyword = searchQuery.value.trim().toLowerCase()
  const sessions = sessionSummaries.value.map((session) => ({
    id: session.id,
    title: session.title,
  }))

  if (!keyword) {
    return sessions
  }

  return sessions.filter((session) => session.title.toLowerCase().includes(keyword))
})

const conversation = computed<ConversationData>(() => ({
  messages: activeSessionState.value?.messages ?? createWelcomeMessages('ChatGPT analysis session'),
  thinkingLabel: isSending.value
    ? isSendingInteraction.value
      ? 'Uploading file and analyzing data...'
      : 'Processing with ChatGPT...'
    : isUploading.value
      ? 'Uploading dataset...'
      : isRunningAnalysis.value
        ? 'Running analysis...'
        : 'Ready for your next prompt',
  isThinking: isSending.value || isUploading.value || isRunningAnalysis.value,
}))

const composer = computed<ComposerData>(() => {
  const chips: ComposerChip[] = []

  chips.push({
    icon: authStatus.value.connected ? 'smart_toy' : 'analytics',
    label: authStatus.value.connected ? 'ChatGPT connected' : 'Backend analysis mode',
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
      icon: 'description',
      label: activeDataset.value.filename,
      tone: 'primary',
    })
  }

  const extraDatasetCount = Math.max((activeSessionState.value?.datasets.length ?? 0) - 1, 0)
  if (extraDatasetCount > 0) {
    chips.push({
      icon: 'dataset',
      label: `+${extraDatasetCount} more`,
      tone: 'neutral',
    })
  }

  if (isUploading.value) {
    chips.push({
      icon: 'progress_activity',
      label: 'Uploading',
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

const analyticsPayload = computed(() => activeSessionState.value?.analyticsPayload ?? null)
const workspacePayload = computed(() => activeSessionState.value?.workspacePayload ?? null)

watch(analyticsPaneWidth, (width) => {
  window.localStorage.setItem(ANALYTICS_PANE_WIDTH_STORAGE_KEY, String(clampAnalyticsPaneWidth(width)))
})

onMounted(async () => {
  const controller = new AbortController()
  restoreAnalyticsPaneWidth()
  window.addEventListener('message', handleOpenAiAuthMessage)
  window.addEventListener('focus', handleWindowFocus)

  try {
    const health = await fetchHealthcheck(controller.signal)
    connectionStatus.value = health.status === 'ok' ? 'connected' : 'offline'
  } catch {
    connectionStatus.value = 'offline'
  }

  await loadAuthStatus()
  await loadSessions()
})

onUnmounted(() => {
  if (authPollTimer !== null) {
    window.clearInterval(authPollTimer)
  }
  stopAnalyticsPaneResize()
  window.removeEventListener('message', handleOpenAiAuthMessage)
  window.removeEventListener('focus', handleWindowFocus)
  authPopup = null
})
</script>

<template>
  <div class="portal-layout">
    <PortalSidebar
      :sidebar="{ ...shellSidebar, recentSessions }"
      :active-session-id="activeSessionId"
      @primary-action="handlePrimaryAction"
      @select-session="selectSession"
    />

    <div class="portal-main-shell">
      <PortalHeader
        :header="shellHeader"
        :search-query="searchQuery"
        :connection-status="connectionStatus"
        :auth-status="authStatus"
        :is-connecting="isConnecting"
        @connect-open-ai="connectOpenAi"
        @search-change="handleSearchChange"
      />

      <p v-if="authError" class="auth-error">{{ authError }}</p>

      <div
        class="portal-main-grid"
        :class="{ 'portal-main-grid--resizing': isResizingAnalyticsPane }"
        :style="{ '--analytics-pane-width': `${analyticsPaneWidth}px` }"
      >
      <PortalConversationPane
          :conversation="conversation"
          :composer="composer"
          :send-disabled="isSending || isRunningAnalysis"
          :attach-disabled="isUploading || isRunningAnalysis"
          :error-message="chatError || uploadError"
          :attached-file-name="pendingAttachment?.name ?? null"
          :attached-file-meta="pendingAttachment ? `${formatFileSize(pendingAttachment.size)} · 메시지와 함께 전송` : null"
          @attach="openInteractionPicker"
          @drop-file="queueInteractionFile"
          @remove-attachment="clearPendingAttachment"
          @send="handleSendMessage"
        />
        <button
          class="pane-resizer"
          type="button"
          aria-label="분석 패널 너비 조절"
          @pointerdown="startAnalyticsPaneResize"
        >
          <span></span>
        </button>
        <PortalAnalyticsPane
          :analytics="shellAnalytics"
          :analytics-payload="analyticsPayload"
          :workspace-payload="workspacePayload"
          :dataset-asset="activeDataset"
          :is-loading="isSending || isUploading || isRunningAnalysis"
          :error-message="analyticsError"
          @prompt-click="handleSuggestedPrompt"
          @insight-action="handleInsightAction"
        />
      </div>
    </div>

    <button class="floating-action" type="button" aria-label="Run analysis" @click="runAnalysis">
      <span class="material-symbols-outlined">add</span>
    </button>

    <input
      ref="interactionPickerRef"
      class="dataset-picker"
      type="file"
      accept=".csv,.tsv,.xls,.xlsx,.json,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      @change="handleInteractionFileChange"
    />

    <input
      ref="datasetPickerRef"
      class="dataset-picker"
      type="file"
      accept=".csv,.tsv,.xls,.xlsx,.json,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      @change="handleDatasetFileChange"
    />
  </div>
</template>

<style scoped>
.portal-layout {
  position: relative;
  height: 100vh;
  display: grid;
  grid-template-columns: 288px minmax(0, 1fr);
  gap: 24px;
  padding: 24px;
  overflow: hidden;
}

.portal-main-shell {
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 20px;
  overflow: hidden;
}

.portal-main-grid {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 20px minmax(320px, var(--analytics-pane-width, 420px));
  gap: 0;
  align-items: stretch;
}

.portal-main-grid--resizing {
  user-select: none;
  cursor: col-resize;
}

.pane-resizer {
  position: relative;
  width: 20px;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
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
  box-shadow: 0 -7px 0 rgba(24, 74, 140, 0.22), 0 7px 0 rgba(24, 74, 140, 0.22);
  transition: background-color 180ms ease, box-shadow 180ms ease, transform 180ms ease;
}

.pane-resizer::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 20px;
  height: 34px;
  border-radius: 999px;
  transform: translate(-50%, -50%);
  background: transparent;
  transition: background-color 180ms ease;
}

.pane-resizer:hover span,
.portal-main-grid--resizing .pane-resizer span {
  background: rgba(24, 74, 140, 0.42);
  box-shadow: 0 -7px 0 rgba(24, 74, 140, 0.42), 0 7px 0 rgba(24, 74, 140, 0.42);
  transform: translate(-50%, -50%) scale(1.08);
}

.pane-resizer:hover::before,
.portal-main-grid--resizing .pane-resizer::before {
  background: rgba(24, 74, 140, 0.05);
}

.auth-error {
  margin: -8px 4px 0;
  color: #9b3b3b;
  font-size: 0.86rem;
}

.floating-action {
  position: fixed;
  right: 28px;
  bottom: 28px;
  width: 60px;
  height: 60px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 20px;
  border: 0;
  color: #fff;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-strong) 100%);
  box-shadow: 0 18px 32px rgba(16, 56, 104, 0.24);
  cursor: pointer;
  transition: transform 180ms ease, box-shadow 180ms ease;
}

.floating-action:hover {
  transform: translateY(-2px);
  box-shadow: 0 22px 40px rgba(16, 56, 104, 0.28);
}

.dataset-picker {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

@media (max-width: 1280px) {
  .portal-layout {
    grid-template-columns: 248px minmax(0, 1fr);
  }

  .portal-main-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 20px;
  }

  .pane-resizer {
    display: none;
  }
}

@media (max-width: 960px) {
  .portal-layout {
    grid-template-columns: minmax(0, 1fr);
    padding: 16px;
  }

  .floating-action {
    right: 18px;
    bottom: 18px;
    width: 54px;
    height: 54px;
    border-radius: 18px;
  }
}
</style>
