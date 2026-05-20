export type {
  DatasetAsset,
  DatasetColumnProfile,
  DatasetLibraryItem,
  DatasetPreview,
  DatasetProfile,
  DatasetSourceTreeItem,
} from '@/features/data-source/types'
export type {
  BackendConnectionStatus,
  LinkedDatasetSummary,
  OpenAiAuthState,
  OpenAiAuthStatus,
  PortalNavItem,
  PortalScreen,
  PortalSidebarData,
  SessionItem,
  WorkspaceItem,
} from '@/layouts/portal/types'

export type NavItem = import('@/layouts/portal/types').PortalNavItem
export type AnalysisScreen = import('@/layouts/portal/types').PortalScreen
export type SidebarData = import('@/layouts/portal/types').PortalSidebarData
export interface HeaderData {
  searchPlaceholder: string
  actions: string[]
}

export interface MessageCodeBlock {
  language: string
  content: string
}

export interface MessageListItem {
  text: string
}

export interface MessageAttachmentPreview {
  filename: string
  meta?: string
  columns: string[]
  rows: Record<string, string | number | null>[]
}

export interface MessageAttachmentStatus {
  filename: string
  meta?: string
}

export interface ChatSubMessage {
  id: string
  type: string
  text: string
  isStreaming: boolean
}

export interface PlanStep {
  step: string
  status: 'pending' | 'in_progress' | 'completed'
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  author?: string
  text: string
  subMessages?: ChatSubMessage[]
  attachmentStatus?: MessageAttachmentStatus
  usedTools?: string[]
   plan?: PlanStep[]
   planExplanation?: string
  codeBlock?: MessageCodeBlock
  bullets?: MessageListItem[]
  attachmentPreview?: MessageAttachmentPreview
}

export interface ComposerChip {
  icon: string
  label: string
  tone?: 'primary' | 'neutral'
}

export interface ComposerData {
  chips: ComposerChip[]
  placeholder: string
}

export interface ConversationData {
  messages: ChatMessage[]
  thinkingLabel: string
  isThinking?: boolean
}

export interface SharedAnalysisSnapshot {
  id: string
  title: string
  fileName: string
  content: string
  createdAt: string
}

export interface MetricCard {
  label: string
  value: string
  meta?: string
  tone?: 'primary' | 'warning'
}

export interface ChartPoint {
  label: string
  spend: number
}

export interface TableRow {
  channel: string
  roi: string
  trend: 'up' | 'flat'
}

export interface InsightData {
  title: string
  body: string
  actionLabel: string
}

export interface AnalyticsData {
  title: string
  chartTitle: string
  chartChange: string
  chartPoints: ChartPoint[]
  metrics: MetricCard[]
  tableRows: TableRow[]
  insight: InsightData
}

export interface AnalyticsChartSeries {
  name: string
  data: Array<number | string | null>
}

export type AnalyticsChartId =
  | 'trend_line'
  | 'category_bar'
  | 'category_area'
  | 'correlation_scatter'
  | 'segment_bubble'
  | 'share_donut'

export type AnalyticsChartType = 'line' | 'bar' | 'area' | 'scatter' | 'bubble' | 'donut' | 'table' | 'metric'

export interface AnalyticsChartPointPayload {
  x: number
  y: number
  label?: string | null
  size?: number | null
  category?: string | null
}

export interface AnalyticsChartMeta {
  x_label?: string | null
  y_label?: string | null
}

export interface AnalyticsChartPayload {
  id?: AnalyticsChartId | null
  type: AnalyticsChartType
  title: string
  x: string[]
  series: AnalyticsChartSeries[]
  points?: AnalyticsChartPointPayload[]
  meta?: AnalyticsChartMeta | null
}

export interface AnalyticsTableColumn {
  key: string
  label: string
}

export interface AnalyticsTablePayload {
  title: string
  columns: AnalyticsTableColumn[]
  rows: Record<string, string | number | null>[]
}

export interface AnalyticsSummaryCard {
  label: string
  value: string
  detail?: string | null
  tone?: 'primary' | 'warning' | 'neutral'
}

export interface AnalyticsInsight {
  title: string
  body: string
  action_label?: string | null
}

export interface AnalyticsPayload {
  summary_cards: AnalyticsSummaryCard[]
  charts: AnalyticsChartPayload[]
  tables: AnalyticsTablePayload[]
  insights: AnalyticsInsight[]
  dataset_profile?: {
    row_count: number
    column_count: number
    columns: Array<{
      name: string
      dtype: string
      null_ratio: number
      sample_values: string[]
    }>
  } | null
}

export type WorkspaceTemplateId =
  | 'overview'
  | 'chart_focus'
  | 'table_focus'
  | 'dataset_profile'
  | 'executive_summary'
  | 'correlation_focus'
  | 'trend_story'
  | 'anomaly_watch'
  | 'comparison_board'

export type WorkspaceSectionKind =
  | 'summary_cards'
  | 'chart'
  | 'table'
  | 'insight'
  | 'dataset_profile'

export interface WorkspaceSectionPayload {
  kind: WorkspaceSectionKind
  title?: string | null
  chart_index?: number | null
  table_index?: number | null
  insight_index?: number | null
  max_items?: number | null
  summary_card_labels?: string[]
}

export interface WorkspacePayload {
  template_id: WorkspaceTemplateId
  title: string
  description?: string | null
  sections: WorkspaceSectionPayload[]
}

export interface AnalysisDashboardData {
  sidebar: SidebarData
  header: HeaderData
  conversation: ConversationData
  composer: ComposerData
  analytics: AnalyticsData
}
