export interface NavItem {
  label: string
  icon: string
  active?: boolean
}

export interface SessionItem {
  title: string
}

export interface SidebarData {
  productName: string
  productTagline: string
  primaryNav: NavItem[]
  recentSessions: SessionItem[]
  secondaryNav: NavItem[]
  profile: {
    name: string
    plan: string
    initials: string
  }
}

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

export interface ChatMessage {
  role: 'user' | 'assistant'
  author?: string
  text: string
  codeBlock?: MessageCodeBlock
  bullets?: MessageListItem[]
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

export interface PortalDashboardData {
  sidebar: SidebarData
  header: HeaderData
  conversation: ConversationData
  composer: ComposerData
  analytics: AnalyticsData
}
