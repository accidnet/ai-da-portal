import type {
  AnalyticsPayload,
  ChatMessage,
  DatasetAsset,
  WorkspacePayload,
} from '../types'
import type {
  DatasetInfoResponse,
  DatasetProfileResponse,
  DatasetPreviewResponse,
  SessionSnapshotDatasetResponse,
  SessionSnapshotMessageResponse,
  SessionSnapshotResponse,
} from '../../../shared/api/portalApi'

export interface SessionRuntimeState {
  title: string
  messages: ChatMessage[]
  analyticsPayload: AnalyticsPayload | null
  workspacePayload: WorkspacePayload | null
  datasets: DatasetAsset[]
  preferredDatasetId: string | null
}

export function mapDatasetProfile(payload: DatasetProfileResponse['profile']): DatasetAsset['profile'] {
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

export function mapDatasetAsset(payload: SessionSnapshotDatasetResponse): DatasetAsset {
  return {
    id: payload.detail.id,
    filename: payload.detail.filename,
    createdAt: payload.detail.created_at,
    preview: {
      columns: payload.preview.columns,
      rows: payload.preview.rows,
    },
    profile: mapDatasetProfile(payload.profile.profile),
  }
}

export function mapDatasetInfoToAsset(payload: {
  detail: DatasetInfoResponse
  preview?: DatasetPreviewResponse | null
  profile?: DatasetProfileResponse | null
}): DatasetAsset {
  return {
    id: payload.detail.id,
    filename: payload.detail.filename,
    createdAt: payload.detail.created_at,
    preview: payload.preview
      ? {
          columns: payload.preview.columns,
          rows: payload.preview.rows,
        }
      : null,
    profile: payload.profile ? mapDatasetProfile(payload.profile.profile) : null,
  }
}

export function mapSnapshotMessage(payload: SessionSnapshotMessageResponse): ChatMessage | null {
  const text = payload.text?.trim() || payload.content?.trim() || ''
  const bullets = (payload.bullets ?? [])
    .map((bullet) => {
      if (typeof bullet === 'string') {
        return bullet.trim()
      }

      return bullet.text?.trim() ?? ''
    })
    .filter(Boolean)
    .map((bullet) => ({ text: bullet }))
  const codeContent = payload.code_block?.content?.trim() ?? ''

  if (!text && bullets.length === 0 && !codeContent) {
    return null
  }

  return {
    role: payload.role,
    author: payload.author ?? (payload.role === 'assistant' ? 'AI 데이터 분석가' : undefined),
    text,
    route: payload.route ?? undefined,
    usedTools: payload.used_tools ?? [],
    plan: payload.plan ?? [],
    planExplanation: payload.plan_explanation?.trim() || undefined,
    bullets,
    codeBlock: codeContent
      ? {
          language: payload.code_block?.language?.trim() || 'text',
          content: codeContent,
        }
      : undefined,
  }
}

export function mapSnapshotToSessionState(
  snapshot: SessionSnapshotResponse,
  createWelcomeMessages: (title: string) => ChatMessage[],
): SessionRuntimeState {
  const title = snapshot.workspace?.title?.trim() || snapshot.session.title
  const datasetOrder = new Map(snapshot.dataset_ids.map((datasetId, index) => [datasetId, index]))
  const datasets = snapshot.datasets
    .map(mapDatasetAsset)
    .sort((left, right) => {
      const leftIndex = datasetOrder.get(left.id) ?? Number.MAX_SAFE_INTEGER
      const rightIndex = datasetOrder.get(right.id) ?? Number.MAX_SAFE_INTEGER
      return leftIndex - rightIndex
    })
  const messages = snapshot.messages
    .map(mapSnapshotMessage)
    .filter((message): message is ChatMessage => message !== null)

  return {
    title,
    messages: messages.length > 0 ? messages : createWelcomeMessages(title),
    analyticsPayload: snapshot.analytics,
    workspacePayload: snapshot.workspace,
    datasets,
    preferredDatasetId: snapshot.session.preferred_dataset_id ?? null,
  }
}
