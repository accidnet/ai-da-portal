export interface HealthcheckResponse {
  status: string
}

export interface OpenAiAuthStatusResponse {
  state: 'disconnected' | 'pending' | 'connected'
  connected: boolean
  pending: boolean
  account_email: string | null
  account_id: string | null
  expires_at: string | null
  scopes: string[]
}

export interface OpenAiAuthorizeResponse {
  authorization_url: string
  expires_at: string
}

export interface OpenAiLogoutResponse {
  success?: boolean
  state?: 'disconnected'
}

export interface SessionSummaryResponse {
  id: string
  title: string
  created_at?: string
  updated_at: string
  message_count?: number
  dataset_count?: number
  preferred_dataset_id?: string | null
  last_dataset?: {
    id: string
    filename: string
  } | null
}

export interface SessionDetailResponse extends SessionSummaryResponse {
  created_at: string
}

export interface SessionUpdatePayload {
  title?: string
  preferred_dataset_id?: string | null
}

export interface SessionTitleResponse {
  session_id: string
  title: string
}

export interface DatasetInfoResponse {
  id: string
  filename: string
  storage_path: string | null
  created_at: string
}

export interface SessionDeleteResponse {
  id: string
  deleted: boolean
}

export interface SessionDatasetLinkResponse {
  session_id: string
  dataset_ids: string[]
}

export interface DatasetLibraryResponse {
  id: string
  filename: string
  storage_path: string | null
  created_at: string
  row_count: number
  column_count: number
  linked_session_count: number
  linked_session_ids: string[]
  latest_used_at: string | null
}

export interface DatasetPreviewResponse {
  dataset_id: string
  columns: string[]
  rows: Array<Record<string, string | number | null>>
}

export interface DatasetProfileResponse {
  dataset_id: string
  profile: {
    row_count: number
    column_count: number
    columns: Array<{
      name: string
      dtype: string
      null_ratio: number
      min_value?: string | number | null
      max_value?: string | number | null
      sample_values: string[]
    }>
  }
}

export type ChatRoute = 'conversation' | 'dataset_analysis' | 'analysis_request'

export type ChatStatus = 'queued' | 'profiling' | 'running_analysis' | 'completed' | 'failed'

export interface SessionSnapshotMessageResponse {
  role: 'user' | 'assistant'
  author?: string | null
  text?: string | null
  dataset_ids?: string[] | null
  route?: ChatRoute | null
  used_tools?: string[] | null
  plan?: Array<{
    step: string
    status: 'pending' | 'in_progress' | 'completed'
  }> | null
  plan_explanation?: string | null
  sub_messages?: Array<{
    id: string
    type: string
    text: string
    is_streaming?: boolean | null
  }> | null
  content?: string | null
  bullets?: Array<{ text?: string | null } | string> | null
  code_block?: {
    language?: string | null
    content?: string | null
  } | null
}

export interface SessionSnapshotDatasetResponse {
  detail: DatasetInfoResponse
  preview: DatasetPreviewResponse
  profile: DatasetProfileResponse
}

export interface SessionSnapshotResponse {
  session: SessionDetailResponse
  messages: SessionSnapshotMessageResponse[]
  dataset_ids: string[]
  datasets: SessionSnapshotDatasetResponse[]
  analytics: ChatResponse['analytics'] | null
  workspace: ChatResponse['workspace'] | null
}

export interface ChatResponse {
  assistant_message: string
  used_tools: string[]
  plan: Array<{
    step: string
    status: 'pending' | 'in_progress' | 'completed'
  }>
  plan_explanation?: string | null
  analytics: {
    summary_cards: Array<{
      label: string
      value: string
      detail?: string | null
      tone?: 'primary' | 'warning' | 'neutral'
    }>
    charts: Array<{
      id?: 'trend_line' | 'category_bar' | 'category_area' | 'correlation_scatter' | 'share_donut' | null
      type: 'line' | 'bar' | 'area' | 'scatter' | 'donut' | 'table' | 'metric'
      title: string
      x: string[]
      series: Array<{ name: string; data: Array<number | string | null> }>
      points?: Array<{ x: number; y: number; label?: string | null }>
      meta?: {
        x_label?: string | null
        y_label?: string | null
      } | null
    }>
    tables: Array<{
      title: string
      columns: Array<{ key: string; label: string }>
      rows: Array<Record<string, string | number | null>>
    }>
    insights: Array<{
      title: string
      body: string
      action_label?: string | null
    }>
    dataset_profile?: {
      row_count: number
      column_count: number
      columns: Array<{
        name: string
        dtype: string
        null_ratio: number
        min_value?: string | number | null
        max_value?: string | number | null
        sample_values: string[]
      }>
    } | null
  } | null
  workspace: {
    template_id:
      | 'overview'
      | 'chart_focus'
      | 'table_focus'
      | 'dataset_profile'
      | 'executive_summary'
      | 'correlation_focus'
      | 'trend_story'
      | 'anomaly_watch'
      | 'comparison_board'
    title: string
    description?: string | null
    sections: Array<{
      kind: 'summary_cards' | 'chart' | 'table' | 'insight' | 'dataset_profile'
      title?: string | null
      chart_index?: number | null
      table_index?: number | null
      insight_index?: number | null
      max_items?: number | null
      summary_card_labels?: string[]
    }>
  } | null
}

export interface AgentStateStreamPayload {
  route: ChatRoute
  assistant_message: string
  used_tools: ChatResponse['used_tools']
  plan: ChatResponse['plan']
  plan_explanation?: string | null
  status: ChatStatus
  analytics: ChatResponse['analytics'] | null
  workspace: ChatResponse['workspace'] | null
  resolved_dataset_id?: string | null
  analysis_type?: string | null
}

export interface ChatSubMessageStreamEvent {
  type: string
  call_id?: string
  item_id?: string
  name?: string | null
  delta?: string
  arguments?: string
  text?: string
  response_id?: string | null
}

export interface AgentChartStreamPayload {
  dataset_id?: string | null
  chart: NonNullable<ChatResponse['analytics']>['charts'][number]
}

export interface AgentPlanStreamPayload {
  ok: boolean
  data?: {
    message?: string
    explanation?: string | null
    plan?: ChatResponse['plan']
  } | null
  errors?: Array<{ message: string; target_id?: string | null }>
  error?: string | null
}

interface ChatStreamEvent {
  type?: string
  delta?: string
  text?: string
  arguments?: string
  call_id?: string
  item_id?: string
  name?: string | null
  response_id?: string | null
  detail?: string
  state?: AgentStateStreamPayload
  dataset_id?: string | null
  chart?: NonNullable<ChatResponse['analytics']>['charts'][number]
  ok?: boolean
  data?: AgentPlanStreamPayload['data']
  errors?: AgentPlanStreamPayload['errors']
  error?: string | null
  response?: ChatResponse
}

export interface StreamChatMessageOptions {
  signal?: AbortSignal
  onAgentIterationStart?: () => void
  onDelta?: (delta: string) => void
  onSubMessage?: (event: ChatSubMessageStreamEvent) => void
  onState?: (state: AgentStateStreamPayload) => void
  onChart?: (payload: AgentChartStreamPayload) => void
  onPlan?: (payload: AgentPlanStreamPayload) => void
}

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'

export function getPortalApiBaseUrl(): string {
  return (import.meta.env.VITE_PORTAL_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, '')
}

/**
 * SSE 프레임 경계를 줄바꿈 형식과 무관하게 찾습니다.
 */
function findSseEventBoundary(buffer: string): { index: number; length: number } | null {
  const match = /\r?\n\r?\n/.exec(buffer)
  if (!match || match.index < 0) return null
  return { index: match.index, length: match[0].length }
}

export async function fetchHealthcheck(signal?: AbortSignal): Promise<HealthcheckResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/health`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (!response.ok) {
    throw new Error(`Healthcheck failed with status ${response.status}`)
  }

  return (await response.json()) as HealthcheckResponse
}

export async function fetchOpenAiAuthStatus(
  signal?: AbortSignal,
): Promise<OpenAiAuthStatusResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/auth/openai/status`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (!response.ok) {
    throw new Error(`OpenAI auth status failed with status ${response.status}`)
  }

  return (await response.json()) as OpenAiAuthStatusResponse
}

export async function authorizeOpenAi(signal?: AbortSignal): Promise<OpenAiAuthorizeResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/auth/openai/authorize`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (!response.ok) {
    throw new Error(`OpenAI authorize failed with status ${response.status}`)
  }

  return (await response.json()) as OpenAiAuthorizeResponse
}

export async function logoutOpenAi(signal?: AbortSignal): Promise<OpenAiLogoutResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/auth/openai/logout`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (!response.ok) {
    throw new Error(`OpenAI logout failed with status ${response.status}`)
  }

  return (await response.json()) as OpenAiLogoutResponse
}

export async function createSession(
  title: string,
  signal?: AbortSignal,
): Promise<SessionDetailResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/sessions`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ title }),
    signal,
  })

  if (!response.ok) {
    throw new Error(`Session create failed with status ${response.status}`)
  }

  return (await response.json()) as SessionDetailResponse
}

export async function resolveSessionTitle(
  sessionId: string,
  userMessage: string,
  signal?: AbortSignal,
): Promise<SessionTitleResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/sessions/${sessionId}/title`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ user_message: userMessage }),
    signal,
  })

  if (!response.ok) {
    throw new Error(`Session title resolve failed with status ${response.status}`)
  }

  return (await response.json()) as SessionTitleResponse
}

export async function fetchSessions(signal?: AbortSignal): Promise<SessionSummaryResponse[]> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/sessions`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (!response.ok) {
    throw new Error(`Session list failed with status ${response.status}`)
  }

  return (await response.json()) as SessionSummaryResponse[]
}

async function patchSession(
  sessionId: string,
  payload: SessionUpdatePayload,
  signal?: AbortSignal,
): Promise<SessionDetailResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/sessions/${sessionId}`, {
    method: 'PATCH',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    let detail = ''
    try {
      const errorBody = (await response.json()) as { detail?: string }
      detail = errorBody.detail?.trim() ?? ''
    } catch {
      detail = ''
    }

    throw new Error(detail || `Session update failed with status ${response.status}`)
  }

  return (await response.json()) as SessionDetailResponse
}

export async function updateSessionTitle(
  sessionId: string,
  title: string,
  signal?: AbortSignal,
): Promise<SessionDetailResponse> {
  return patchSession(sessionId, { title }, signal)
}

export async function updateSessionPreferredDataset(
  sessionId: string,
  preferredDatasetId: string | null,
  signal?: AbortSignal,
): Promise<SessionDetailResponse> {
  return patchSession(sessionId, { preferred_dataset_id: preferredDatasetId }, signal)
}

export async function deleteSession(
  sessionId: string,
  signal?: AbortSignal,
): Promise<SessionDeleteResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (!response.ok) {
    let detail = ''
    try {
      const errorBody = (await response.json()) as { detail?: string }
      detail = errorBody.detail?.trim() ?? ''
    } catch {
      detail = ''
    }

    throw new Error(detail || `Session delete failed with status ${response.status}`)
  }

  return (await response.json()) as SessionDeleteResponse
}

export async function fetchSessionSnapshot(
  sessionId: string,
  signal?: AbortSignal,
): Promise<SessionSnapshotResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/sessions/${sessionId}/snapshot`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (!response.ok) {
    let detail = ''
    try {
      const errorBody = (await response.json()) as { detail?: string }
      detail = errorBody.detail?.trim() ?? ''
    } catch {
      detail = ''
    }

    throw new Error(detail || `Session snapshot failed with status ${response.status}`)
  }

  return (await response.json()) as SessionSnapshotResponse
}

export async function streamChatMessage(
  payload: {
    sessionId: string
    message: string
    datasetIds?: string[]
    attachedDatasetIds?: string[]
  },
  options: StreamChatMessageOptions = {},
): Promise<ChatResponse> {
  const headers: Record<string, string> = {
    Accept: 'text/event-stream',
    'Content-Type': 'application/json',
  }

  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/chat/messages/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      session_id: payload.sessionId,
      message: payload.message,
      uploaded_dataset_ids: payload.datasetIds ?? [],
      attached_dataset_ids: payload.attachedDatasetIds ?? [],
    }),
    signal: options.signal,
  })

  if (!response.ok) {
    let detail = ''
    try {
      const errorBody = (await response.json()) as { detail?: string }
      detail = errorBody.detail?.trim() ?? ''
    } catch {
      detail = ''
    }

    throw new Error(detail || `Chat stream request failed with status ${response.status}`)
  }

  if (!response.body) {
    throw new Error('Chat stream response body is missing.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completedResponse: ChatResponse | null = null

  const processEvent = (event: ChatStreamEvent, fallbackType = '') => {
    const eventType = fallbackType || event.type

    if (
      (eventType === 'response.output_text.delta' || eventType === 'message.delta')
      && typeof event.delta === 'string'
    ) {
      options.onDelta?.(event.delta)
      return
    }

    if (eventType === 'agent.iteration.start') {
      options.onAgentIterationStart?.()
      return
    }

    if (eventType === 'agent.iteration.chart' && event.chart) {
      options.onChart?.({
        dataset_id: event.dataset_id,
        chart: event.chart,
      })
      return
    }

    if (eventType === 'agent.iteration.plan' && typeof event.ok === 'boolean') {
      options.onPlan?.({
        ok: event.ok,
        data: event.data,
        errors: event.errors,
        error: event.error,
      })
      return
    }

    if (eventType && eventType !== 'response.output_text.done' && eventType !== 'message.completed') {
      const isReservedEvent =
        eventType === 'agent.state'
        || eventType === 'agent.iteration.start'
        || eventType === 'agent.iteration.chart'
        || eventType === 'agent.iteration.plan'
        || eventType === 'agent.iteration.done'
        || eventType === 'chat.completed'
        || eventType === 'response.completed'
        || eventType === 'message.completed'
        || eventType === 'error'

      if (!isReservedEvent && (typeof event.delta === 'string' || typeof event.arguments === 'string' || typeof event.text === 'string')) {
        options.onSubMessage?.({
          type: eventType,
          call_id: event.call_id,
          item_id: event.item_id,
          name: event.name,
          delta: event.delta,
          arguments: event.arguments,
          text: event.text,
          response_id: event.response_id,
        })
        return
      }
    }

    if (eventType === 'agent.state' && event.state) {
      options.onState?.(event.state)
      return
    }

    if (
      (
        eventType === 'chat.completed'
        || eventType === 'message.completed'
        || eventType === 'response.completed'
      )
      && event.response
    ) {
      completedResponse = event.response
      return
    }

    if (eventType === 'error') {
      throw new Error(event.detail?.trim() || 'Chat stream failed.')
    }
  }

  const processChunk = (chunk: string) => {
    const trimmed = chunk.trim()
    if (!trimmed) return

    if (!trimmed.includes('data:')) {
      processEvent(JSON.parse(trimmed) as ChatStreamEvent)
      return
    }

    const lines = trimmed.split(/\r?\n/)
    let fallbackType = ''
    const dataLines: string[] = []

    for (const line of lines) {
      if (line.startsWith('event:')) {
        fallbackType = line.slice(6).trim()
        continue
      }

      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart())
      }
    }

    if (dataLines.length === 0) return
    processEvent(JSON.parse(dataLines.join('\n')) as ChatStreamEvent, fallbackType)
  }

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })

    let boundary = findSseEventBoundary(buffer)
    while (boundary) {
      const chunk = buffer.slice(0, boundary.index)
      buffer = buffer.slice(boundary.index + boundary.length)
      processChunk(chunk)
      boundary = findSseEventBoundary(buffer)
    }

    if (done) break
  }

  if (buffer.trim()) {
    processChunk(buffer)
  }

  if (completedResponse) {
    return completedResponse
  }

  throw new Error('Chat stream ended without a completed response.')
}

export async function uploadDataset(
  file: File,
  sessionId: string,
  signal?: AbortSignal,
): Promise<DatasetInfoResponse> {
  const formData = new FormData()
  formData.append('file', file)

  formData.append('session_id', sessionId)

  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/datasets/upload`, {
    method: 'POST',
    body: formData,
    signal,
  })

  if (!response.ok) {
    let detail = ''
    try {
      const errorBody = (await response.json()) as { detail?: string }
      detail = errorBody.detail?.trim() ?? ''
    } catch {
      detail = ''
    }

    throw new Error(detail || `Dataset upload failed with status ${response.status}`)
  }

  return (await response.json()) as DatasetInfoResponse
}

export async function fetchDatasetPreview(
  datasetId: string,
  signal?: AbortSignal,
): Promise<DatasetPreviewResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/datasets/${datasetId}/preview`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (!response.ok) {
    throw new Error(`Dataset preview failed with status ${response.status}`)
  }

  return (await response.json()) as DatasetPreviewResponse
}

export async function fetchDatasetProfile(
  datasetId: string,
  signal?: AbortSignal,
): Promise<DatasetProfileResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/datasets/${datasetId}/profile`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (!response.ok) {
    throw new Error(`Dataset profile failed with status ${response.status}`)
  }

  return (await response.json()) as DatasetProfileResponse
}

export async function fetchDatasets(signal?: AbortSignal): Promise<DatasetLibraryResponse[]> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/datasets`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (!response.ok) {
    let detail = ''
    try {
      const errorBody = (await response.json()) as { detail?: string }
      detail = errorBody.detail?.trim() ?? ''
    } catch {
      detail = ''
    }

    throw new Error(detail || `Dataset list failed with status ${response.status}`)
  }

  return (await response.json()) as DatasetLibraryResponse[]
}

export async function attachDatasetToSession(
  sessionId: string,
  datasetId: string,
  signal?: AbortSignal,
): Promise<SessionDatasetLinkResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/sessions/${sessionId}/datasets`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ dataset_id: datasetId }),
    signal,
  })

  if (!response.ok) {
    let detail = ''
    try {
      const errorBody = (await response.json()) as { detail?: string }
      detail = errorBody.detail?.trim() ?? ''
    } catch {
      detail = ''
    }

    throw new Error(detail || `Dataset attach failed with status ${response.status}`)
  }

  return (await response.json()) as SessionDatasetLinkResponse
}

export async function detachDatasetFromSession(
  sessionId: string,
  datasetId: string,
  signal?: AbortSignal,
): Promise<SessionDatasetLinkResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/sessions/${sessionId}/datasets/${datasetId}`, {
    method: 'DELETE',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (!response.ok) {
    let detail = ''
    try {
      const errorBody = (await response.json()) as { detail?: string }
      detail = errorBody.detail?.trim() ?? ''
    } catch {
      detail = ''
    }

    throw new Error(detail || `Dataset detach failed with status ${response.status}`)
  }

  return (await response.json()) as SessionDatasetLinkResponse
}

export async function deleteDataset(
  datasetId: string,
  signal?: AbortSignal,
): Promise<DatasetInfoResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/datasets/${datasetId}`, {
    method: 'DELETE',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (!response.ok) {
    let detail = ''
    try {
      const errorBody = (await response.json()) as { detail?: string }
      detail = errorBody.detail?.trim() ?? ''
    } catch {
      detail = ''
    }

    throw new Error(detail || `Dataset delete failed with status ${response.status}`)
  }

  return (await response.json()) as DatasetInfoResponse
}
