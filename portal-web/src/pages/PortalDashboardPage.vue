<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import PortalAnalyticsPane from '../features/portal/components/PortalAnalyticsPane.vue'
import PortalConversationPane from '../features/portal/components/PortalConversationPane.vue'
import PortalHeader from '../features/portal/components/PortalHeader.vue'
import PortalSidebar from '../features/portal/components/PortalSidebar.vue'
import type {
  AnalyticsData,
  ChatMessage,
  ComposerChip,
  ComposerData,
  ConversationData,
  HeaderData,
  MessageAttachmentPreview,
  OpenAiAuthStatus,
  SessionItem,
  SidebarData,
} from '../features/portal/types'
import {
  type SessionRuntimeState,
  mapDatasetAsset,
  mapSnapshotToSessionState,
} from '../features/portal/utils/sessionState'
import {
  authorizeOpenAi,
  type ChatInteractionResponse,
  createAnalysis,
  createSession,
  fetchDatasetPreview,
  fetchDatasetProfile,
  fetchHealthcheck,
  fetchOpenAiAuthStatus,
  fetchSessionSnapshot,
  fetchSessions,
  sendChatInteraction,
  sendChatMessage,
  uploadDataset,
} from '../shared/api/portalApi'

interface OpenAiPopupMessage {
  source?: string
  status?: 'success' | 'error'
  error?: string
  account_email?: string
}

const OPENAI_AUTH_POPUP_SOURCE = 'portal-openai-auth'
const ANALYTICS_PANE_WIDTH_STORAGE_KEY = 'portal.analyticsPaneWidth'
const DEFAULT_SESSION_TITLE = 'ChatGPT 분석 세션'
const LOCAL_SESSION_ID = 'local-session'

const shellSidebar: SidebarData = {
  productName: '데이터 분석 AI',
  productTagline: '데이터 인텔리전스',
  primaryNav: [
    { label: '새 분석', icon: 'add_chart', active: true },
    { label: '기록', icon: 'history' },
    { label: '데이터 소스', icon: 'database' },
    { label: '모델', icon: 'neurology' },
  ],
  recentSessions: [],
  secondaryNav: [
    { label: '설정', icon: 'settings' },
    { label: '도움말', icon: 'help' },
  ],
  profile: {
    name: 'Alex Architect',
    plan: 'Pro Plan',
    initials: 'AA',
  },
}

const shellHeader: HeaderData = {
  searchPlaceholder: '분석, 데이터셋, 프롬프트 검색',
  actions: ['notifications', 'ios_share', 'account_circle'],
}

const shellAnalytics: AnalyticsData = {
  title: '분석 작업공간',
  chartTitle: '실시간 분석 대기 중',
  chartChange: '아직 분석 결과가 없어요',
  chartPoints: [],
  metrics: [],
  tableRows: [],
  insight: {
    title: '여기서 시작해 보세요',
    body: '데이터셋을 업로드하거나 프롬프트를 보내면 이 영역에 실시간 분석 결과가 채워집니다.',
    actionLabel: '분석 실행',
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
const isAnalyticsFullscreen = ref(false)
const searchQuery = ref('')
const analyticsPaneWidth = ref(420)
const isResizingAnalyticsPane = ref(false)
const activeSessionId = ref<string | null>(null)
const sessionSummaries = ref<SessionItem[]>([])
const sessionStates = ref<Record<string, SessionRuntimeState>>({})
const hydratedSessionIds = ref<Record<string, boolean>>({})
const datasetPickerRef = ref<HTMLInputElement | null>(null)
const interactionPickerRef = ref<HTMLInputElement | null>(null)
const pendingAttachment = ref<File | null>(null)
const exportMessage = ref<string | null>(null)
let authPollTimer: number | null = null
let authPopup: Window | null = null
let latestSnapshotRequestId = 0

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

function createWelcomeMessages(): ChatMessage[] {
  return [
    {
      role: 'assistant',
      author: 'AI 데이터 분석가',
      text: '데이터셋을 업로드하면 바로 분석을 시작할 수 있어요.',
      bullets: [
        { text: 'CSV 또는 스프레드시트 파일 업로드하기' },
        { text: '추세, 상관관계, 이상치 분석 요청하기' },
        { text: '간단한 그래프 시각화하기' },
      ],
    },
  ]
}

function normalizeAssistantMessage(message: string): string {
  let normalizedMessage = message.trim()

  normalizedMessage = normalizedMessage.replace(/^\[(?:Pasted?|Past)\s*/i, '')

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
    messages: createWelcomeMessages(),
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
  return `분석 세션 ${sessionSummaries.value.length + 1}`
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
    authError.value = 'ChatGPT 연결 상태를 불러오지 못했어요.'
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
    authError.value = event.data.error ?? 'ChatGPT 연결을 완료하지 못했어요.'
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
      const created = await createSession(DEFAULT_SESSION_TITLE)
      sessionSummaries.value = [{ id: created.id, title: created.title }]
      activeSessionId.value = created.id
      ensureSessionState(created.id, created.title)
      hydratedSessionIds.value[created.id] = true
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

    if (activeSessionId.value) {
      await hydrateSessionSnapshot(activeSessionId.value)
    }
  } catch {
    if (!activeSessionId.value) {
      const fallback = LOCAL_SESSION_ID
      activeSessionId.value = fallback
      sessionSummaries.value = [{ id: fallback, title: DEFAULT_SESSION_TITLE }]
      ensureSessionState(fallback, DEFAULT_SESSION_TITLE)
      hydratedSessionIds.value[fallback] = true
    }
  }
}

function getActiveSessionId(): string {
  if (activeSessionId.value) {
    return activeSessionId.value
  }

  const fallback = LOCAL_SESSION_ID
  activeSessionId.value = fallback
  ensureSessionState(fallback, DEFAULT_SESSION_TITLE)
  updateSessionSummary(fallback, DEFAULT_SESSION_TITLE)
  hydratedSessionIds.value[fallback] = true
  return fallback
}

async function ensureActiveSession() {
  const currentSessionId = getActiveSessionId()
  const state = sessionStates.value[currentSessionId]
  if (state) {
    return currentSessionId
  }

  const created = await createSession(DEFAULT_SESSION_TITLE)
  activeSessionId.value = created.id
  sessionSummaries.value = [{ id: created.id, title: created.title }, ...sessionSummaries.value]
  ensureSessionState(created.id, created.title)
  hydratedSessionIds.value[created.id] = true
  return created.id
}

async function hydrateSessionSnapshot(sessionId: string, force = false) {
  if (!sessionId || sessionId === LOCAL_SESSION_ID) {
    return
  }

  const summary = sessionSummaries.value.find((session) => session.id === sessionId)
  ensureSessionState(sessionId, summary?.title ?? DEFAULT_SESSION_TITLE)

  if (hydratedSessionIds.value[sessionId] && !force) {
    return
  }

  const requestId = ++latestSnapshotRequestId

  try {
    const snapshot = await fetchSessionSnapshot(sessionId)
    if (requestId !== latestSnapshotRequestId) {
      return
    }

    const state = mapSnapshotToSessionState(snapshot, createWelcomeMessages)
    sessionStates.value[sessionId] = state
    updateSessionSummary(sessionId, state.title)
    hydratedSessionIds.value[sessionId] = true
  } catch {
    hydratedSessionIds.value[sessionId] = true
  }
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
    hydratedSessionIds.value[created.id] = true
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
    authError.value = 'ChatGPT 연결을 시작하지 못했어요.'
  } finally {
    syncAuthPolling()
  }
}

async function selectSession(sessionId: string) {
  activeSessionId.value = sessionId
  const summary = sessionSummaries.value.find((session) => session.id === sessionId)
  ensureSessionState(sessionId, summary?.title ?? DEFAULT_SESSION_TITLE)
  await hydrateSessionSnapshot(sessionId, true)
}

function handlePrimaryAction(label: string) {
  if (label === '새 분석') {
    void createAndSelectSession()
  }
}

function handleSearchChange(value: string) {
  searchQuery.value = value
}

function toggleAnalyticsFullscreen() {
  isAnalyticsFullscreen.value = !isAnalyticsFullscreen.value
}

function sanitizeFileNameSegment(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9가-힣]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'analysis-report'
}

function buildReportContent() {
  const sessionState = activeSessionState.value
  const dataset = activeDataset.value
  const analytics = analyticsPayload.value
  const workspace = workspacePayload.value
  const lines: string[] = []

  lines.push(`# ${workspace?.title ?? sessionState?.title ?? DEFAULT_SESSION_TITLE}`)

  if (workspace?.description) {
    lines.push('', workspace.description)
  }

  if (dataset) {
    lines.push('', '## 데이터셋')
    lines.push(`- 파일명: ${dataset.filename}`)
    lines.push(`- 생성 시각: ${dataset.createdAt}`)
    if (dataset.profile) {
      lines.push(`- 행/열: ${dataset.profile.rowCount}행 / ${dataset.profile.columnCount}열`)
    }
  }

  if (analytics?.summary_cards?.length) {
    lines.push('', '## 핵심 지표')
    for (const card of analytics.summary_cards) {
      lines.push(`- ${card.label}: ${card.value}${card.detail ? ` (${card.detail})` : ''}`)
    }
  }

  if (analytics?.insights?.length) {
    lines.push('', '## 인사이트')
    for (const insight of analytics.insights) {
      lines.push(`### ${insight.title}`)
      lines.push(insight.body)
      if (insight.action_label) {
        lines.push(`- 제안 액션: ${insight.action_label}`)
      }
      lines.push('')
    }
    while (lines.at(-1) === '') {
      lines.pop()
    }
  }

  if (analytics?.charts?.length) {
    lines.push('', '## 차트')
    for (const chart of analytics.charts) {
      lines.push(`### ${chart.title}`)
      for (const series of chart.series) {
        lines.push(`- ${series.name}: ${series.data.map((value, index) => `${chart.x[index] ?? index}=${value ?? '-'}`).join(', ')}`)
      }
    }
  }

  if (analytics?.tables?.length) {
    lines.push('', '## 표')
    for (const table of analytics.tables) {
      lines.push(`### ${table.title}`)
      lines.push(table.columns.map((column) => column.label).join(' | '))
      lines.push(table.columns.map(() => '---').join(' | '))
      for (const row of table.rows) {
        lines.push(table.columns.map((column) => String(row[column.key] ?? '-')).join(' | '))
      }
      lines.push('')
    }
    while (lines.at(-1) === '') {
      lines.pop()
    }
  }

  if (dataset?.profile?.columns?.length) {
    lines.push('', '## 컬럼 프로파일')
    for (const column of dataset.profile.columns) {
      const samples = column.sampleValues.length ? ` / 예시: ${column.sampleValues.join(', ')}` : ''
      lines.push(`- ${column.name}: ${column.dtype} / 결측 ${Math.round(column.nullRatio * 100)}%${samples}`)
    }
  }

  if (sessionState?.messages?.length) {
    lines.push('', '## 최근 대화')
    for (const message of sessionState.messages.slice(-6)) {
      const speaker = message.role === 'assistant' ? (message.author ?? 'AI 데이터 분석가') : '사용자'
      lines.push(`- ${speaker}: ${message.text}`)
    }
  }

  return lines.join('\n')
}

function exportAnalyticsReport() {
  const content = buildReportContent().trim()
  if (!content) {
    return
  }

  const fileName = `${sanitizeFileNameSegment(activeSessionState.value?.title ?? DEFAULT_SESSION_TITLE)}.md`
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  window.URL.revokeObjectURL(url)
  exportMessage.value = `${fileName} 리포트를 다운로드했어요.`
}

async function handleSendMessage(message: string) {
  chatError.value = null
  uploadError.value = null
  analyticsError.value = null
  exportMessage.value = null

  const sessionId = await ensureActiveSession()
  const sessionState = ensureSessionState(sessionId, DEFAULT_SESSION_TITLE)
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
      const dataset = mapDatasetAsset(interactionDataset)
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
        text: normalizeAssistantMessage(response.assistant_message),
      },
    ]
    sessionState.analyticsPayload = response.analytics
    sessionState.workspacePayload = response.workspace
    updateSessionSummary(sessionId, sessionState.title)
  } catch (error) {
    chatError.value = error instanceof Error
      ? error.message
      : '메시지를 보내지 못했어요. ChatGPT 연결과 백엔드 상태를 확인해 주세요.'
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
    meta: `${formatFileSize(size)} · ${preview.rows.length}행 미리보기`,
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
  exportMessage.value = null
  isUploading.value = true

  try {
    const sessionId = await ensureActiveSession()
    const detail = await uploadDataset(file, sessionId)
    const [preview, profile] = await Promise.all([
      fetchDatasetPreview(detail.id),
      fetchDatasetProfile(detail.id),
    ])

    const dataset = mapDatasetAsset({ detail, preview, profile })

    const sessionState = ensureSessionState(sessionId, DEFAULT_SESSION_TITLE)
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
            text: `${dataset.profile?.rowCount ?? 0}행 / ${dataset.profile?.columnCount ?? 0}열 프로파일을 반영했어요`,
          },
          { text: '오른쪽 패널에 서버 기준 미리보기와 프로파일이 반영돼요' },
          { text: '이제 프롬프트 전송과 분석 실행이 같은 데이터셋을 사용해요' },
        ],
      },
    ]
    updateSessionSummary(sessionId, sessionState.title)
    activeSessionId.value = sessionId
  } catch {
    uploadError.value = '데이터셋 업로드에 실패했어요. CSV 또는 스프레드시트 파일로 다시 시도해 주세요.'
  } finally {
    isUploading.value = false
  }
}

async function runAnalysis() {
  analyticsError.value = null
  exportMessage.value = null
  const sessionId = await ensureActiveSession()
  const sessionState = ensureSessionState(sessionId, DEFAULT_SESSION_TITLE)
  const primaryDataset = sessionState.datasets[0]

  if (!primaryDataset) {
    analyticsError.value = '분석을 실행하려면 먼저 데이터셋을 업로드해 주세요.'
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
          '분석이 완료되어 실시간 분석 패널을 업데이트했어요.',
      },
    ]
    updateSessionSummary(sessionId, sessionState.title)
  } catch {
    analyticsError.value = '분석을 시작하지 못했어요. 잠시 후 다시 시도해 주세요.'
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
      icon: 'description',
      label: activeDataset.value.filename,
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

const analyticsPayload = computed(() => activeSessionState.value?.analyticsPayload ?? null)
const workspacePayload = computed(() => activeSessionState.value?.workspacePayload ?? null)
const canExportReport = computed(() => Boolean(
  activeDataset.value
  || analyticsPayload.value?.summary_cards?.length
  || analyticsPayload.value?.charts?.length
  || analyticsPayload.value?.tables?.length
  || analyticsPayload.value?.insights?.length
  || activeSessionState.value?.messages?.length,
))

watch(analyticsPaneWidth, (width) => {
  window.localStorage.setItem(ANALYTICS_PANE_WIDTH_STORAGE_KEY, String(clampAnalyticsPaneWidth(width)))
})

watch(activeSessionId, () => {
  exportMessage.value = null
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
      <p v-if="exportMessage" class="export-message">{{ exportMessage }}</p>

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
          :is-fullscreen="isAnalyticsFullscreen"
          :export-disabled="!canExportReport"
          @prompt-click="handleSuggestedPrompt"
          @insight-action="handleInsightAction"
          @toggle-fullscreen="toggleAnalyticsFullscreen"
          @export-report="exportAnalyticsReport"
        />
      </div>
    </div>

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

.export-message {
  margin: -10px 4px 0;
  color: #1d6b45;
  font-size: 0.86rem;
}

.portal-main-grid--analytics-fullscreen {
  grid-template-columns: minmax(0, 1fr);
}

.portal-main-grid--analytics-fullscreen :deep(.conversation-shell),
.portal-main-grid--analytics-fullscreen .pane-resizer {
  display: none;
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

}
</style>
