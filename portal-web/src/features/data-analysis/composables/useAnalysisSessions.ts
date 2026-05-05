import { ref, watch, type Ref } from 'vue'

import { createSession, deleteSession, fetchSessionSnapshot, fetchSessions, updateSessionTitle } from '../../../shared/api/portalApi'
import type { AnalysisScreen, SessionItem } from '../types'
import {
  ACTIVE_SESSION_STORAGE_KEY,
  DEFAULT_SESSION_TITLE,
  DRAFT_SESSION_ID,
  LOCAL_SESSION_ID,
} from '../constants/analysisPage'
import {
  createSessionState,
  createWelcomeMessages,
  mapSessionSummary,
  resolvePreferredDatasetId,
} from '../utils/analysisPageHelpers'
import { mapSnapshotToSessionState, type SessionRuntimeState } from '../utils/sessionState'

export function useAnalysisSessions(options: {
  currentScreen: Ref<AnalysisScreen>
  onSessionDeleted?: (sessionId: string) => void | Promise<void>
}) {
  const { currentScreen, onSessionDeleted } = options

  const activeSessionId = ref<string | null>(null)
  const sessionSummaries = ref<SessionItem[]>([])
  const sessionStates = ref<Record<string, SessionRuntimeState>>({})
  const hydratedSessionIds = ref<Record<string, boolean>>({})
  const hiddenSessionSummaries = ref<Record<string, SessionItem>>({})
  const sessionHubError = ref<string | null>(null)
  const isSessionMutating = ref(false)

  let latestSnapshotRequestId = 0

  function readStoredActiveSessionId(): string | null {
    if (typeof window === 'undefined') {
      return null
    }

    // 새로고침 후에도 마지막 작업 세션을 복원하기 위해 브라우저 저장값을 사용합니다.
    return window.localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY)
  }

  function writeStoredActiveSessionId(sessionId: string | null) {
    if (typeof window === 'undefined') {
      return
    }

    if (!sessionId) {
      window.localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY)
      return
    }

    // draft 세션도 저장해 사용자가 새 분석 화면에서 새로고침해도 같은 시작 상태를 유지합니다.
    window.localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, sessionId)
  }

  watch(activeSessionId, (sessionId) => {
    writeStoredActiveSessionId(sessionId)
  })

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

  function updateSessionSummary(sessionId: string, patch: Partial<SessionItem>) {
    const current = sessionSummaries.value.find((session) => session.id === sessionId)
    if (current) {
      Object.assign(current, patch)
      sessionSummaries.value = [...sessionSummaries.value]
      return
    }

    const hidden = hiddenSessionSummaries.value[sessionId]
    if (!hidden) {
      return
    }

    hiddenSessionSummaries.value = {
      ...hiddenSessionSummaries.value,
      [sessionId]: {
        ...hidden,
        ...patch,
      },
    }
  }

  function updateSessionTitleLocally(sessionId: string, title: string) {
    const normalizedTitle = title.trim()
    if (!normalizedTitle) {
      return
    }

    const state = ensureSessionState(sessionId, normalizedTitle)
    state.title = normalizedTitle
    updateSessionSummary(sessionId, {
      title: normalizedTitle,
      updatedAt: new Date().toISOString(),
    })
  }

  function syncSessionSummaryWithState(sessionId: string) {
    const state = sessionStates.value[sessionId]
    if (!state) {
      return
    }

    updateSessionSummary(sessionId, {
      title: state.title,
      messageCount: state.messages.length,
      datasetCount: state.datasets.length,
      preferredDatasetId: resolvePreferredDatasetId(state),
      lastDataset: state.datasets[0]
        ? {
            id: state.datasets[0].id,
            filename: state.datasets[0].filename,
          }
        : null,
      updatedAt: new Date().toISOString(),
    })
  }

  function openDraftSession() {
    // 새 분석은 첫 메시지가 전송되기 전까지 서버 목록에 노출하지 않습니다.
    activeSessionId.value = DRAFT_SESSION_ID
    sessionStates.value[DRAFT_SESSION_ID] = createSessionState(DEFAULT_SESSION_TITLE)
    hydratedSessionIds.value[DRAFT_SESSION_ID] = true
    currentScreen.value = 'dashboard'
    sessionHubError.value = null
  }

  function isTemporarySession(sessionId: string | null): boolean {
    return sessionId === DRAFT_SESSION_ID || sessionId === LOCAL_SESSION_ID
  }

  function revealSessionSummary(sessionId: string, fallbackTitle = DEFAULT_SESSION_TITLE) {
    if (isTemporarySession(sessionId) || sessionSummaries.value.some((session) => session.id === sessionId)) {
      return
    }

    const state = sessionStates.value[sessionId]
    const hidden = hiddenSessionSummaries.value[sessionId]
    const now = new Date().toISOString()
    const nextSummary: SessionItem = {
      ...hidden,
      id: sessionId,
      title: state?.title ?? hidden?.title ?? fallbackTitle,
      messageCount: state?.messages.length ?? hidden?.messageCount ?? 0,
      datasetCount: state?.datasets.length ?? hidden?.datasetCount ?? 0,
      preferredDatasetId: state ? resolvePreferredDatasetId(state) : hidden?.preferredDatasetId,
      lastDataset: state?.datasets[0]
        ? {
            id: state.datasets[0].id,
            filename: state.datasets[0].filename,
          }
        : hidden?.lastDataset,
      updatedAt: hidden?.updatedAt ?? now,
      createdAt: hidden?.createdAt,
    }

    sessionSummaries.value = [nextSummary, ...sessionSummaries.value]
    const { [sessionId]: _revealed, ...remainingHiddenSummaries } = hiddenSessionSummaries.value
    hiddenSessionSummaries.value = remainingHiddenSummaries
  }

  async function loadSessions() {
    try {
      const sessions = await fetchSessions()
      sessionSummaries.value = sessions.map(mapSessionSummary)
      if (sessionSummaries.value.length === 0) {
        openDraftSession()
        return
      }

      for (const session of sessionSummaries.value) {
        if (session.id) {
          ensureSessionState(session.id, session.title)
        }
      }

      const preferredSessionId = activeSessionId.value ?? readStoredActiveSessionId()
      if (preferredSessionId === DRAFT_SESSION_ID) {
        openDraftSession()
        return
      }

      if (!preferredSessionId || !sessionSummaries.value.some((session) => session.id === preferredSessionId)) {
        activeSessionId.value = sessionSummaries.value[0]?.id ?? null
      } else {
        activeSessionId.value = preferredSessionId
      }
      if (activeSessionId.value) {
        await hydrateSessionSnapshot(activeSessionId.value)
      }
      sessionHubError.value = null
    } catch {
      if (!activeSessionId.value) {
        activeSessionId.value = LOCAL_SESSION_ID
        sessionSummaries.value = [
          {
            id: LOCAL_SESSION_ID,
            title: DEFAULT_SESSION_TITLE,
            messageCount: 1,
            datasetCount: 0,
          },
        ]
        ensureSessionState(LOCAL_SESSION_ID, DEFAULT_SESSION_TITLE)
        hydratedSessionIds.value[LOCAL_SESSION_ID] = true
      }
      sessionHubError.value = '세션 목록을 서버에서 불러오지 못해 로컬 세션으로 전환했어요.'
    }
  }

  function getActiveSessionId(): string {
    if (activeSessionId.value) {
      return activeSessionId.value
    }

    openDraftSession()
    return DRAFT_SESSION_ID
  }

  async function ensureActiveSession() {
    const currentSessionId = getActiveSessionId()
    if (!isTemporarySession(currentSessionId) && sessionStates.value[currentSessionId]) {
      return currentSessionId
    }

    const created = await createSession(DEFAULT_SESSION_TITLE)
    const previousState = sessionStates.value[currentSessionId]
    activeSessionId.value = created.id
    hiddenSessionSummaries.value = {
      ...hiddenSessionSummaries.value,
      [created.id]: mapSessionSummary(created),
    }
    sessionStates.value[created.id] = previousState ?? createSessionState(created.title)
    sessionStates.value[created.id].title = created.title
    delete sessionStates.value[currentSessionId]
    delete hydratedSessionIds.value[currentSessionId]
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
      updateSessionSummary(sessionId, {
        title: state.title,
        messageCount: state.messages.length,
        datasetCount: state.datasets.length,
        lastDataset: state.datasets[0] ? { id: state.datasets[0].id, filename: state.datasets[0].filename } : null,
        updatedAt: snapshot.session.updated_at,
        createdAt: snapshot.session.created_at,
      })
      hydratedSessionIds.value[sessionId] = true
    } catch {
      hydratedSessionIds.value[sessionId] = true
    }
  }

  async function createAndSelectSession() {
    openDraftSession()
  }

  async function selectSession(sessionId: string, targetScreen: AnalysisScreen = currentScreen.value) {
    activeSessionId.value = sessionId
    currentScreen.value = targetScreen
    const summary = sessionSummaries.value.find((session) => session.id === sessionId)
    ensureSessionState(sessionId, summary?.title ?? DEFAULT_SESSION_TITLE)
    await hydrateSessionSnapshot(sessionId, true)
  }

  async function handleRenameSession(payload: { sessionId: string; title: string }) {
    try {
      isSessionMutating.value = true
      const updated = await updateSessionTitle(payload.sessionId, payload.title)
      updateSessionSummary(payload.sessionId, {
        title: updated.title,
        updatedAt: updated.updated_at,
      })
      const state = sessionStates.value[payload.sessionId]
      if (state) {
        state.title = updated.title
      }
      sessionHubError.value = null
    } catch (error) {
      sessionHubError.value = error instanceof Error ? error.message : '세션 제목을 수정하지 못했어요.'
    } finally {
      isSessionMutating.value = false
    }
  }

  async function handleDeleteSession(sessionId: string) {
    try {
      isSessionMutating.value = true
      await deleteSession(sessionId)
      sessionSummaries.value = sessionSummaries.value.filter((session) => session.id !== sessionId)
      delete sessionStates.value[sessionId]
      delete hydratedSessionIds.value[sessionId]
      delete hiddenSessionSummaries.value[sessionId]
      await onSessionDeleted?.(sessionId)
      if (activeSessionId.value === sessionId) {
        const nextSessionId = sessionSummaries.value[0]?.id ?? null
        activeSessionId.value = nextSessionId
        if (nextSessionId) {
          await selectSession(nextSessionId, 'dashboard')
        } else {
          openDraftSession()
        }
      }
      sessionHubError.value = null
    } catch (error) {
      sessionHubError.value = error instanceof Error ? error.message : '세션을 삭제하지 못했어요.'
    } finally {
      isSessionMutating.value = false
    }
  }

  return {
    activeSessionId,
    sessionSummaries,
    sessionStates,
    hydratedSessionIds,
    sessionHubError,
    isSessionMutating,
    ensureSessionState,
    updateSessionSummary,
    updateSessionTitleLocally,
    syncSessionSummaryWithState,
    loadSessions,
    getActiveSessionId,
    ensureActiveSession,
    revealSessionSummary,
    hydrateSessionSnapshot,
    createAndSelectSession,
    selectSession,
    handleRenameSession,
    handleDeleteSession,
  }
}
