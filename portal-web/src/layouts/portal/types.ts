export interface PortalNavItem {
  label: string
  icon: string
  active?: boolean
  screen?: PortalScreen
  action?: 'create-session'
}

export type PortalScreen = 'dashboard' | 'datasets'
export type PortalAnalysisViewMode = 'default' | 'workspace'

export interface LinkedDatasetSummary {
  id: string
  filename: string
}

export interface WorkspaceItem {
  id: string
  name: string
  createdAt: string
  updatedAt: string
}

export interface SessionItem {
  id?: string
  workspaceId?: string | null
  title: string
  createdAt?: string
  updatedAt?: string
  messageCount?: number
  datasetCount?: number
  lastDataset?: LinkedDatasetSummary | null
  preferredDatasetId?: string | null
}

export interface PortalSidebarData {
  productName: string
  productTagline: string
  primaryNav: PortalNavItem[]
  recentSessions: SessionItem[]
}

export type BackendConnectionStatus = 'checking' | 'connected' | 'offline'
export type OpenAiAuthState = 'disconnected' | 'pending' | 'connected'

export interface OpenAiAuthStatus {
  state: OpenAiAuthState
  connected: boolean
  pending: boolean
  accountEmail: string | null
  accountId: string | null
  expiresAt: string | null
  scopes: string[]
}
