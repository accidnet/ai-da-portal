import type { AnalyticsData, SidebarData } from '../types'

export const OPENAI_AUTH_POPUP_SOURCE = 'portal-openai-auth'
// 기존 브라우저 저장값과 공유 링크를 유지하기 위해 storage key는 변경하지 않습니다.
export const ANALYTICS_PANE_WIDTH_STORAGE_KEY = 'portal.analyticsPaneWidth'
export const SIDEBAR_WIDTH_STORAGE_KEY = 'portal.sidebarWidth'
export const ANALYSIS_RIGHT_PANE_MODE_STORAGE_KEY = 'portal.analysisRightPaneMode'
export const ACTIVE_SESSION_STORAGE_KEY = 'portal.activeSessionId'
export const ANALYSIS_SHARE_STORAGE_PREFIX = 'portal.analysis-share.'
export const DEFAULT_SESSION_TITLE = 'ChatGPT 분석 세션'
export const LOCAL_SESSION_ID = 'local-session'
export const DRAFT_SESSION_ID = 'draft-analysis-session'

export const shellSidebar: SidebarData = {
  productName: 'AI 데이터 분석',
  productTagline: 'AI 데이터 분석 포탈',
  primaryNav: [
    { label: '새로운 분석', icon: 'add_chart', screen: 'dashboard', action: 'create-session' },
    { label: '데이터 소스', icon: 'database', screen: 'datasets' },
  ],
  recentSessions: [],
}

export const shellAnalytics: AnalyticsData = {
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
