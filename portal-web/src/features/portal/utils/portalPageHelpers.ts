import type {
  AnalyticsPayload,
  ChatMessage,
  DatasetLibraryItem,
  MessageAttachmentPreview,
  PortalScreen,
  SessionItem,
  WorkspacePayload,
} from '../types'
import { DEFAULT_SESSION_TITLE, SCREEN_HASHES } from '../constants/portalPage'
import type { SessionRuntimeState } from './sessionState'
import type {
  DatasetLibraryResponse,
  OpenAiAuthStatusResponse,
  SessionSummaryResponse,
} from '../../../shared/api/portalApi'

export function resolveScreenFromHash(hash = window.location.hash): PortalScreen {
  const normalizedHash = hash.trim().toLowerCase()
  if (normalizedHash === SCREEN_HASHES.sessions) return 'sessions'
  if (normalizedHash === SCREEN_HASHES.datasets) return 'datasets'
  return 'dashboard'
}

export function clampAnalyticsPaneWidth(width: number): number {
  return Math.min(Math.max(width, 320), 720)
}

export function mapSessionSummary(session: SessionSummaryResponse): SessionItem {
  return {
    id: session.id,
    title: session.title,
    createdAt: session.created_at,
    updatedAt: session.updated_at,
    messageCount: session.message_count ?? 0,
    datasetCount: session.dataset_count ?? 0,
    preferredDatasetId: session.preferred_dataset_id ?? null,
    lastDataset: session.last_dataset ?? null,
  }
}

export function mapDatasetLibraryItem(dataset: DatasetLibraryResponse): DatasetLibraryItem {
  return {
    id: dataset.id,
    filename: dataset.filename,
    contentType: dataset.content_type,
    storagePath: dataset.storage_path,
    createdAt: dataset.created_at,
    rowCount: dataset.row_count,
    columnCount: dataset.column_count,
    linkedSessionCount: dataset.linked_session_count,
    linkedSessionIds: dataset.linked_session_ids,
    latestUsedAt: dataset.latest_used_at,
    preview: null,
    profile: null,
  }
}

export function mapOpenAiAuthStatus(status: OpenAiAuthStatusResponse) {
  return {
    state: status.state,
    connected: status.connected,
    pending: status.pending,
    accountEmail: status.account_email,
    accountId: status.account_id,
    expiresAt: status.expires_at,
    scopes: status.scopes,
  }
}

export function createWelcomeMessages(): ChatMessage[] {
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

export function normalizeAssistantMessage(message: string): string {
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

export function createSessionState(title: string): SessionRuntimeState {
  return {
    title,
    messages: createWelcomeMessages(),
    analyticsPayload: null,
    workspacePayload: null,
    datasets: [],
    preferredDatasetId: null,
  }
}

export function resolvePreferredDatasetId(
  state: SessionRuntimeState | null | undefined,
): string | null {
  if (!state) return null
  if (state.preferredDatasetId && state.datasets.some((dataset) => dataset.id === state.preferredDatasetId)) {
    return state.preferredDatasetId
  }

  return state.datasets[0]?.id ?? null
}

export function sanitizeFileNameSegment(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9가-힣]+/g, '-').replace(/^-+|-+$/g, '') || 'analysis-report'
}

export function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export function createAttachmentPreview(
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

export function buildReportContent(payload: {
  sessionState: SessionRuntimeState | null
  dataset: SessionRuntimeState['datasets'][number] | null
  analytics: AnalyticsPayload | null
  workspace: WorkspacePayload | null
}): string {
  const { sessionState, dataset, analytics, workspace } = payload
  const lines: string[] = []
  lines.push(`# ${workspace?.title ?? sessionState?.title ?? DEFAULT_SESSION_TITLE}`)
  if (workspace?.description) {
    lines.push('', workspace.description)
  }
  if (dataset) {
    lines.push('', '## 데이터셋', `- 파일명: ${dataset.filename}`, `- 생성 시각: ${dataset.createdAt}`)
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
      lines.push(`### ${insight.title}`, insight.body)
      if (insight.action_label) {
        lines.push(`- 제안 액션: ${insight.action_label}`)
      }
      lines.push('')
    }
    while (lines.at(-1) === '') lines.pop()
  }
  if (analytics?.charts?.length) {
    lines.push('', '## 차트')
    for (const chart of analytics.charts) {
      lines.push(`### ${chart.title}`)
      for (const series of chart.series) {
        lines.push(
          `- ${series.name}: ${series.data.map((value, index) => `${chart.x[index] ?? index}=${value ?? '-'}`).join(', ')}`,
        )
      }
    }
  }
  if (analytics?.tables?.length) {
    lines.push('', '## 표')
    for (const table of analytics.tables) {
      lines.push(`### ${table.title}`, table.columns.map((column) => column.label).join(' | '), table.columns.map(() => '---').join(' | '))
      for (const row of table.rows) {
        lines.push(table.columns.map((column) => String(row[column.key] ?? '-')).join(' | '))
      }
      lines.push('')
    }
    while (lines.at(-1) === '') lines.pop()
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

export function isUploadableDatasetFile(file: File): boolean {
  const name = file.name.toLowerCase()
  return (
    name.endsWith('.csv') ||
    file.type.includes('csv') ||
    file.type.startsWith('text/') ||
    name.endsWith('.tsv') ||
    name.endsWith('.xls') ||
    name.endsWith('.xlsx') ||
    name.endsWith('.json')
  )
}
