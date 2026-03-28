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

export interface SessionSummaryResponse {
  id: string
  title: string
  updated_at: string
}

export interface SessionDetailResponse extends SessionSummaryResponse {
  created_at: string
}

export interface DatasetDetailResponse {
  id: string
  filename: string
  content_type: string | null
  storage_path: string
  created_at: string
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
  assistant_message: string
  follow_up_suggestions: Array<string>
  status: 'queued' | 'profiling' | 'running_analysis' | 'completed' | 'failed'
  analytics: {
    summary_cards: Array<{
      label: string
      value: string
      detail?: string | null
      tone?: 'primary' | 'warning' | 'neutral'
    }>
    charts: Array<{
      type: 'line' | 'bar' | 'scatter' | 'table' | 'metric'
      title: string
      x: string[]
      series: Array<{ name: string; data: Array<number | string | null> }>
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

export interface ChatInteractionResponse extends ChatResponse {
  dataset: {
    detail: DatasetDetailResponse
    preview: DatasetPreviewResponse
    profile: DatasetProfileResponse
  } | null
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

export async function sendChatInteraction(
  payload: { sessionId: string; message: string; datasetIds?: string[]; file?: File | null },
  signal?: AbortSignal,
): Promise<ChatInteractionResponse> {
  const formData = new FormData()
  formData.append('session_id', payload.sessionId)
  formData.append('message', payload.message)
  formData.append('dataset_ids_json', JSON.stringify(payload.datasetIds ?? []))

  if (payload.file) {
    formData.append('file', payload.file)
  }

  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/chat/interactions`, {
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

    throw new Error(detail || `Chat interaction failed with status ${response.status}`)
  }

  return (await response.json()) as ChatInteractionResponse
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
