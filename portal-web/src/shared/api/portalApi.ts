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

export interface DatasetDetailResponse {
  id: string
  filename: string
  content_type: string | null
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
  content_type: string | null
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
      sample_values: string[]
    }>
    suggested_prompts: string[]
  }
}

export interface SessionSnapshotMessageResponse {
  role: 'user' | 'assistant'
  author?: string | null
  text?: string | null
  route?: 'conversation' | 'dataset_analysis' | 'analysis_request' | null
  used_tools?: string[] | null
  plan?: Array<{
    step: string
    status: 'pending' | 'in_progress' | 'completed'
  }> | null
  plan_explanation?: string | null
  content?: string | null
  bullets?: Array<{ text?: string | null } | string> | null
  code_block?: {
    language?: string | null
    content?: string | null
  } | null
}

export interface SessionSnapshotDatasetResponse {
  detail: DatasetDetailResponse
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
  session_id: string
  session_title?: string | null
  assistant_message: string
  route: 'conversation' | 'dataset_analysis' | 'analysis_request'
  used_tools: string[]
  plan: Array<{
    step: string
    status: 'pending' | 'in_progress' | 'completed'
  }>
  plan_explanation?: string | null
  status: 'queued' | 'profiling' | 'running_analysis' | 'completed' | 'failed'
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
        sample_values: string[]
      }>
    suggested_prompts: string[]
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

export interface ChatInteractionDataset {
  detail: DatasetDetailResponse
  preview: DatasetPreviewResponse
  profile: DatasetProfileResponse
}

export interface AgentStateStreamPayload {
  route: ChatResponse['route']
  assistant_message: string
  used_tools: ChatResponse['used_tools']
  plan: ChatResponse['plan']
  plan_explanation?: string | null
  status: ChatResponse['status']
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
  response?: ChatResponse
  dataset?: ChatInteractionDataset | null
}

export interface StreamChatMessageOptions {
  signal?: AbortSignal
  onDelta?: (delta: string) => void
  onSubMessage?: (event: ChatSubMessageStreamEvent) => void
  onState?: (state: AgentStateStreamPayload) => void
  onDataset?: (dataset: ChatInteractionDataset) => void
}

export interface AnalysisResponse {
  id: string
  session_id: string
  dataset_id: string | null
  analysis_type: string
  status: 'queued' | 'profiling' | 'running_analysis' | 'completed' | 'failed'
  created_at: string
  analytics: ChatResponse['analytics']
  workspace: ChatResponse['workspace']
}

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'

export function getPortalApiBaseUrl(): string {
  return (import.meta.env.VITE_PORTAL_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, '')
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

export async function sendChatMessage(
  payload: { sessionId: string; message: string; datasetIds?: string[] },
  signal?: AbortSignal,
): Promise<ChatResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/chat/messages`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: payload.sessionId,
      message: payload.message,
      dataset_ids: payload.datasetIds ?? [],
    }),
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

    throw new Error(detail || `Chat request failed with status ${response.status}`)
  }

  return (await response.json()) as ChatResponse
}

export async function streamChatMessage(
  payload: { sessionId: string; message: string; datasetIds?: string[]; file?: File | null },
  options: StreamChatMessageOptions = {},
): Promise<ChatResponse> {
  const headers: Record<string, string> = {
    Accept: 'text/event-stream',
  }
  let body: BodyInit

  if (payload.file) {
    const formData = new FormData()
    formData.append('session_id', payload.sessionId)
    formData.append('message', payload.message)
    formData.append('dataset_ids_json', JSON.stringify(payload.datasetIds ?? []))
    formData.append('file', payload.file)
    body = formData
  } else {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify({
      session_id: payload.sessionId,
      message: payload.message,
      dataset_ids: payload.datasetIds ?? [],
    })
  }

  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/chat/messages/stream`, {
    method: 'POST',
    headers,
    body,
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
    const eventType = event.type || fallbackType

    if (eventType === 'response.output_text.delta' && typeof event.delta === 'string') {
      options.onDelta?.(event.delta)
      return
    }

    if (eventType && eventType !== 'response.output_text.done' && eventType !== 'message.completed') {
      const isReservedEvent =
        eventType === 'agent.state'
        || eventType === 'dataset.ready'
        || eventType === 'response.completed'
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

    if (eventType === 'dataset.ready' && event.dataset) {
      options.onDataset?.(event.dataset)
      return
    }

    if (eventType === 'response.completed' && event.response) {
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

    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const chunk = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      processChunk(chunk)
      boundary = buffer.indexOf('\n\n')
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
  sessionId?: string | null,
  signal?: AbortSignal,
): Promise<DatasetDetailResponse> {
  const formData = new FormData()
  formData.append('file', file)

  if (sessionId) {
    formData.append('session_id', sessionId)
  }

  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/datasets/upload`, {
    method: 'POST',
    body: formData,
    signal,
  })

  if (!response.ok) {
    throw new Error(`Dataset upload failed with status ${response.status}`)
  }

  return (await response.json()) as DatasetDetailResponse
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
): Promise<DatasetDetailResponse> {
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

  return (await response.json()) as DatasetDetailResponse
}

export async function createAnalysis(
  payload: {
    sessionId: string
    datasetId?: string | null
    analysisType: string
    prompt?: string | null
  },
  signal?: AbortSignal,
): Promise<AnalysisResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/analyses`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: payload.sessionId,
      dataset_id: payload.datasetId ?? null,
      analysis_type: payload.analysisType,
      prompt: payload.prompt ?? null,
    }),
    signal,
  })

  if (!response.ok) {
    throw new Error(`Analysis creation failed with status ${response.status}`)
  }

  return (await response.json()) as AnalysisResponse
}
